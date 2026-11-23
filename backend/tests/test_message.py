"""Message detector, URL checker, fusion, explainer and message API tests."""
import pytest
from fastapi.testclient import TestClient

from app import advice, explainer, fusion
from app.detectors import message_detector as md
from app.detectors import url_checker as uc
from app.main import app
from app.schemas import AnalysisResult, Signal

client = TestClient(app)

SCAMS = {
    "bank_kyc": "Dear customer, your SBI account will be blocked today. Update your KYC immediately at http://sbi-kyc-update.xyz/login",
    "digital_arrest": "This is CBI officer. An illegal parcel in your name contains narcotics. You are under digital arrest, do not disconnect the video call and tell no one.",
    "family_emergency": "Mom I changed my number. I'm in trouble, please send money urgently and don't tell papa. UPI: rahul123@oksbi",
    "upi_payment": "Please approve the collect request on your UPI app to receive your refund of Rs 4999 immediately.",
    "job_offer": "Work from home part time job, earn Rs 5000 per day. Pay registration fee Rs 999 to confirm your offer letter.",
    "lottery_prize": "Congratulations! You have won the KBC lucky draw jackpot. Claim your prize now by paying the fee.",
    "investment": "Join our VIP group for trading tips with guaranteed returns and daily profit, risk free!",
    "delivery_courier": "Your parcel is held at customs, pay the pending fee to reschedule delivery: bit.ly/3xYz",
    "romance": "My dear, I am a doctor working overseas and stuck at customs. I love you, please send money for the gift parcel.",
}


@pytest.mark.parametrize("expected,text", SCAMS.items())
def test_each_scam_type_detected(expected, text):
    r = md.analyze_message(text)
    assert r["score"] >= 35, (expected, r["score"], r["fired"])
    if expected in ("upi_payment", "family_emergency"):
        assert r["scam_type"] in ("upi_payment", "family_emergency")
    else:
        assert r["scam_type"] == expected, (r["scam_type"], r["fired"])


def test_otp_request_is_high():
    r = md.analyze_message("Sir please share your OTP to complete verification")
    assert r["score"] >= 70 and "otp_request" in r["fired"]


def test_legit_otp_notice_stays_low():
    r = md.analyze_message("123456 is your OTP for login. Do not share it with anyone. -Amazon")
    assert r["score"] < 35 and r["scam_type"] == "likely_legit"
    assert "otp_request" not in r["fired"]


def test_plain_chat_is_low():
    r = md.analyze_message("Hey, are we still meeting for lunch tomorrow at 1? Let me know.")
    assert r["score"] < 35 and r["scam_type"] == "likely_legit"


def test_entities_extracted():
    e = md.extract_entities("Pay Rs 2,500 to ramesh@ybl or call 98765 43210, see http://x.xyz/a. Mail me a@b.com")
    assert "ramesh@ybl" in e["upi_ids"] and "a@b.com" not in e["upi_ids"]
    assert any("98765" in p for p in e["phone_numbers"])
    assert any("2,500" in a for a in e["amounts"])
    assert e["urls"]


def test_highlights_do_not_overlap():
    hl = md.analyze_message(SCAMS["bank_kyc"])["highlights"]
    assert hl
    for a, b in zip(hl, hl[1:]):
        assert a["end"] <= b["start"]


# ---------- URL checker ----------
@pytest.mark.parametrize("url,sid", [
    ("http://192.168.4.5/login", "url_ip_host"),
    ("https://bit.ly/abc", "url_shortener"),
    ("https://xn--pypal-4ve.com", "url_punycode"),
    ("https://paytrn.com/pay", "url_lookalike"),
    ("https://sbi.secure-login.example.xyz/a", "url_brand_mismatch"),
    ("https://google.com@evil.site/x", "url_at_trick"),
    ("https://a.b.c.d.example.com", "url_subdomains"),
    ("https://free-gift.top", "url_suspicious_tld"),
])
def test_url_signals(url, sid):
    assert sid in {s.id for s in uc.analyze_url(url)}


def test_legit_urls_not_brand_flagged():
    for u in ("https://www.amazon.in/gp/help", "https://onlinesbi.sbi/", "https://www.hdfcbank.com/personal"):
        ids = {s.id for s in uc.analyze_url(u)}
        assert not ids & {"url_lookalike", "url_brand_mismatch"}, (u, ids)


def test_url_extraction_ignores_emails_and_trailing_punct():
    urls = [u for u, _, _ in uc.extract_urls("mail a@b.com or visit https://x.xyz/p).")]
    assert urls == ["https://x.xyz/p"]


# ---------- fusion ----------
def test_fusion_bounds():
    sus = [Signal(id="a", name="a", category="image", direction="suspicious", weight=1.0, detail="d")]
    assert fusion.fuse_single(1.0, sus) == 100
    assert fusion.fuse_single(0.0, []) == 0
    assert 0 <= fusion.fuse_single(5.0, sus) <= 100
    assert fusion.fuse_combined({"a": 100, "b": 100}, bonus=50) == 100


def test_combined_not_dragged_down():
    assert fusion.fuse_combined({"image": 90, "audio": 5}) >= 0.6 * 90


def test_risk_levels():
    assert (fusion.risk_level(34), fusion.risk_level(50), fusion.risk_level(66)) == ("low", "medium", "high")


# ---------- explainer ----------
def test_template_explanation_without_key():
    r = md.analyze_message(SCAMS["bank_kyc"])
    ex = explainer.explain("message", r["score"], "high", r["signals"], r["scam_type"])
    assert ex["source"] == "template" and ex["headline"] and "likelihood" in ex["explanation"]
    ids = {s.id for s in r["signals"]}
    assert set(ex["used_signal_ids"]) <= ids


def test_grounding_rejects_ungrounded_sentence():
    sig = [Signal(id="urgency", name="u", category="message", direction="suspicious", weight=0.2, detail="d")]
    kept = explainer.ground_filter([
        {"text": "It pressures you to act fast.", "signal_ids": ["urgency"]},
        {"text": "The sender is located in Nigeria.", "signal_ids": []},
        {"text": "The link was registered yesterday.", "signal_ids": ["not_a_signal"]},
    ], sig)
    assert [k["text"] for k in kept] == ["It pressures you to act fast."]


def test_advice_mentions_reporting_when_high():
    assert any("1930" in s for s in advice.next_steps("message", "high", "bank_kyc"))


# ---------- API ----------
def test_api_message_ok_and_schema():
    r = client.post("/api/analyze/message", json={"text": SCAMS["family_emergency"]})
    assert r.status_code == 200
    res = AnalysisResult(**r.json())
    assert res.risk_level == "high" and res.next_steps and res.limitations and res.signals


def test_api_message_errors():
    assert client.post("/api/analyze/message", json={"text": "   "}).json()["code"] == "empty_text"
    r = client.post("/api/analyze/message", json={"text": "x" * 6000})
    assert r.status_code == 413 and r.json()["code"] == "text_too_long"
