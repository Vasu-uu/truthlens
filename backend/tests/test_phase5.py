"""LLM explainer/classifier (mocked), combined fusion, samples."""
import io

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from PIL import Image

from app import explainer, fusion, llm
from app.detectors import message_detector as md
from app.main import app
from app.schemas import AnalysisResult, Signal

client = TestClient(app)

SIGS = [
    Signal(id="urgency", name="Pressure", category="message", direction="suspicious", weight=0.3, detail="It pushes you to act fast."),
    Signal(id="money_request", name="Money", category="message", direction="suspicious", weight=0.3, detail="It asks for money."),
]


class FakeClient:
    enabled = True
    provider, model = "fake", "m"

    def __init__(self, reply):
        self.reply = reply

    def complete_json(self, system, user):
        return self.reply


def _patch(monkeypatch, reply):
    monkeypatch.setattr(llm, "get_client", lambda: FakeClient(reply))


def test_llm_explanation_accepted_when_grounded(monkeypatch):
    _patch(monkeypatch, {"headline": "Likely a scam", "sentences": [
        {"text": "It pushes you to hurry.", "signal_ids": ["urgency"]},
        {"text": "It also asks for money.", "signal_ids": ["money_request"]}]})
    ex = explainer.explain("message", 80, "high", SIGS)
    assert ex["source"] == "llm" and "hurry" in ex["explanation"]


def test_llm_ungrounded_sentences_dropped_then_fallback(monkeypatch):
    _patch(monkeypatch, {"headline": "x", "sentences": [
        {"text": "The sender is in Nigeria.", "signal_ids": []},
        {"text": "It uses a fake bank logo.", "signal_ids": ["logo"]}]})
    assert explainer.explain("message", 80, "high", SIGS)["source"] == "template"


def test_llm_overclaim_dropped(monkeypatch):
    _patch(monkeypatch, {"headline": "Definitely fake", "sentences": [
        {"text": "This is definitely a scam, 100% sure.", "signal_ids": ["urgency"]},
        {"text": "It asks for money.", "signal_ids": ["money_request"]}]})
    assert explainer.explain("message", 80, "high", SIGS)["source"] == "template"


def test_llm_failure_never_crashes(monkeypatch):
    _patch(monkeypatch, None)
    assert explainer.explain("message", 80, "high", SIGS)["source"] == "template"


def test_llm_provider_none_is_disabled():
    assert llm.LLMClient().enabled is False
    assert llm.extract_json('noise {"a": 1} tail') == {"a": 1} and llm.extract_json("nope") is None


def test_llm_hint_can_boost_but_never_lower():
    text = "Hello, we noticed an unusual login. Please review your account soon."
    base = md.analyze_message(text)["score"]
    boosted = md.analyze_message(text, llm_hint={"scam_type": "bank_kyc", "manipulation_tactics": ["urgency"], "confidence": 0.9})
    assert boosted["score"] >= base and "llm_assessment" in boosted["fired"]
    scam = "Share your OTP now to avoid block"
    low = md.analyze_message(scam, llm_hint={"scam_type": "likely_legit", "manipulation_tactics": [], "confidence": 0.99})
    assert low["score"] >= 70  # hard floor holds against a lenient LLM


# ---------- combined fusion ----------
def test_cross_modal_bonus_rules():
    assert fusion.cross_modal_bonus({"image": 70, "audio": 60, "message": 80}, "family_emergency")[0] == 15
    assert fusion.cross_modal_bonus({"audio": 60, "message": 80}, "family_emergency")[0] == 10
    assert fusion.cross_modal_bonus({"audio": 60, "message": 80}, "other")[0] == 0
    assert fusion.cross_modal_bonus({"audio": 20, "message": 20}, "family_emergency")[0] == 0


def test_combined_endpoint_text_and_audio():
    b = io.BytesIO()
    sf.write(b, (0.1 * np.sin(2 * np.pi * 150 * np.arange(48000) / 16000)).astype(np.float32), 16000, format="WAV")
    msg = "Mom I changed my number. I'm in trouble, send Rs 20,000 urgently to ram@oksbi and don't tell papa."
    r = client.post("/api/analyze/combined", data={"text": msg}, files={"audio": ("a.wav", b.getvalue(), "audio/wav")})
    assert r.status_code == 200, r.text
    res = AnalysisResult(**r.json())
    assert res.modality == "combined" and res.risk_level == "high"
    assert {p["modality"] for p in res.artifacts["per_modality"]} == {"audio", "message"}


def test_combined_all_three_triggers_bonus_signal():
    from app.routers.combined import fuse_results
    mk = lambda m, s: AnalysisResult(modality=m, risk_score=s, risk_level="high", confidence="medium", signals=[],
                                     artifacts={"scam_type": "family_emergency"} if m == "message" else {})
    import time
    res = fuse_results({"image": mk("image", 70), "audio": mk("audio", 60), "message": mk("message", 85)}, time.perf_counter())
    assert "coordinated_impersonation" in {s.id for s in res.signals}
    assert res.risk_score >= 0.6 * 85 and res.risk_score <= 100


def test_combined_no_input_and_weak_modality_not_dragging():
    assert client.post("/api/analyze/combined").json()["code"] == "no_input"
    assert fusion.fuse_combined({"message": 90, "image": 2}) >= 0.6 * 90


# ---------- samples ----------
def test_samples_catalog_and_analyze():
    lst = client.get("/api/samples").json()
    ids = {s["id"] for s in lst}
    assert "msg-scam-son-in-trouble" in ids and "msg-legit-otp" in ids
    assert all("path" not in s for s in lst)
    assert client.post("/api/analyze/sample/msg-scam-son-in-trouble").json()["risk_level"] == "high"
    assert client.post("/api/analyze/sample/msg-legit-otp").json()["risk_level"] == "low"
    assert client.post("/api/analyze/sample/msg-legit-friend").json()["risk_level"] == "low"
    assert client.post("/api/analyze/sample/..%2F..%2Fetc").status_code == 404
    assert client.post("/api/analyze/sample/nope").json()["code"] == "sample_not_found"


def test_llm_explainer_payload_never_contains_message_text(monkeypatch):
    seen = {}

    class Spy(FakeClient):
        def complete_json(self, system, user):
            seen["user"] = user
            return None

    monkeypatch.setattr(llm, "get_client", lambda: Spy(None))
    secret = "http://sbi-kyc-update.xyz/login"
    r = md.analyze_message(f"Your SBI account will be blocked. Update KYC immediately at {secret} and share the OTP")
    assert "sbi-kyc-update" in " ".join(str(s.value) for s in r["signals"])  # the value exists internally...
    explainer.explain("message", r["score"], "high", r["signals"], r["scam_type"])
    assert "sbi-kyc-update" not in seen["user"]  # ...but never reaches the LLM
