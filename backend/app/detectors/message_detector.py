"""Rule-based scam message detector (fully offline). An LLM can optionally refine it."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app import fusion
from app.config import get_settings
from app.detectors import url_checker
from app.schemas import Signal

SCAM_TYPES = [
    "bank_kyc", "digital_arrest", "family_emergency", "upi_payment", "job_offer",
    "lottery_prize", "investment", "delivery_courier", "romance", "other", "likely_legit",
]


@dataclass(frozen=True)
class Rule:
    """A named pattern group that yields one signal."""

    id: str
    name: str
    tactic: str
    weight: float
    types: tuple[str, ...]
    patterns: tuple[str, ...]
    detail: str


RULES: list[Rule] = [
    Rule("urgency", "Pressure to act immediately", "urgency", 0.25, (),
         (r"\b(immediately|urgent(ly)?|right now|asap|within \d+\s*(hours?|hrs?|minutes?|mins?)|last chance|expires? (today|soon|in)|act now|hurry|final (notice|warning)|today only|before midnight)\b",
          r"\b(turant|abhi|jaldi|foran)\b", r"\b(udane|udan|ippol thanne|vegam)\b"),
         "The message pushes you to act fast, which stops you from checking whether it is genuine."),
    Rule("threat_block", "Threat of blocking or closing your account", "threat", 0.25, ("bank_kyc",),
         (r"\byour (account|card|sim|number|service|connection|upi|wallet)\b[^.\n]{0,40}\b(blocked|suspended|deactivated|disconnected|closed|frozen|freeze|expire[ds]?)\b",
          r"\b(will be|has been|is being) (blocked|suspended|deactivated|disconnected)\b", r"\bkhata (band|block)\b"),
         "It threatens to block or close something you rely on, a common way to scare people into obeying."),
    Rule("money_request", "Request to send money", "money", 0.30, (),
         (r"\b(send|transfer|pay|deposit|remit)\b[^.\n]{0,40}\b(money|amount|rs\.?|₹|inr|rupees|funds?|payment|fees?)\b",
          r"\b(gift ?cards?|google play card|itunes card|bitcoin|crypto|usdt)\b",
          r"\b(need|require) (some |urgent )?(money|cash|funds?)\b", r"\b(paisa|paise|paisay) (bhejo|bhej|do)\b", r"\bpanam (ayakku|tharu)\b",
          r"\bpay\b[^.\n]{0,20}\bupi\b"),
         "It asks you to send money, which is the real goal of most scams."),
    Rule("upi_collect", "Asks you to approve a payment request", "money", 0.35, ("upi_payment",),
         (r"\b(approve|accept)\b[^.\n]{0,25}\b(request|collect)\b", r"\bscan (this |the )?qr\b[^.\n]{0,30}\b(receive|refund|get)\b",
          r"\bcollect request\b"),
         "Approving a 'collect' request or scanning a QR to 'receive' money actually takes money out of your account."),
    Rule("authority", "Claims to be a bank, government or official body", "authority", 0.20, (),
         (r"\b(rbi|reserve bank|income tax|trai|police|customs|cyber ?crime|nodal officer|sbi|hdfc|icici|axis bank|paytm|bank manager|electricity board|telecom department)\b",),
         "It claims to come from an official body, a favourite disguise because people tend to obey authority."),
    Rule("kyc_update", "KYC / account verification demand", "authority", 0.30, ("bank_kyc",),
         (r"\b(update|complete|verify|expire[ds]?|pending)\b[^.\n]{0,20}\b(kyc|pan|aadhaar|aadhar)\b", r"\bkyc\b[^.\n]{0,30}\b(update|expire|pending|verification|suspend)\w*\b",
          r"\b(net ?banking|debit card|credit card)\b[^.\n]{0,30}\b(blocked|expired|suspended|deactivated)\b"),
         "Banks do not ask you to 'update KYC' through links or messages; this is a very common phishing script."),
    Rule("digital_arrest", "'Digital arrest' / legal-threat script", "authority", 0.45, ("digital_arrest",),
         (r"\b(digital arrest|arrest warrant|money laundering|narcotics|illegal (parcel|goods)|parcel (contains|seized|is seized)|cbi|ncb|ed officer|enforcement directorate|supreme court|stay on (the )?(video )?call|do not disconnect|case (has been )?(registered|filed) against you)\b",),
         "There is no such thing as a 'digital arrest'; real agencies never demand money or video-call custody."),
    Rule("secrecy", "Asks you to keep it secret", "secrecy", 0.20, ("family_emergency", "digital_arrest"),
         (r"\b(keep (this|it) (a )?(secret|confidential|private)|don'?t tell (anyone|anybody|papa|mom|dad|mummy)|do not (tell|inform|discuss)|do not tell anyone|dont tell anyone|kisi ko mat batana|aarodum parayaruthu)\b",),
         "Scammers isolate victims by asking for secrecy so nobody can warn them."),
    Rule("family_emergency", "Family-emergency script", "family", 0.40, ("family_emergency",),
         (r"\b(i (have )?changed my number|this is my new number|my new number|lost my phone|phone (is )?(broken|damaged|not working))\b",
          r"\b(mom|mum|mummy|dad|papa|maa|amma|achan|bhaiya|didi|uncle|aunty)\b[^.\n]{0,40}\b(trouble|accident|hospital|emergency|arrested|police|help)\b",
          r"\bi'?m in (trouble|danger|jail|hospital)\b", r"\bi (got|was) (arrested|in an accident)\b"),
         "This follows the classic 'family member in trouble / new number' script used to extract quick payments."),
    Rule("prize", "Prize or lottery claim", "prize", 0.35, ("lottery_prize",),
         (r"\b(you (have )?won|lottery|lucky (draw|winner)|jackpot|congratulations[^.\n]{0,30}(won|selected|winner)|kbc|claim your (prize|reward|gift))\b",),
         "Unexpected prizes are bait; genuine contests do not ask you to pay or share details to collect."),
    Rule("job_fee", "Job offer that asks for a fee", "job", 0.40, ("job_offer",),
         (r"\b(registration|processing|training|security|joining|refundable|kit)\s+(fee|deposit|charges?|amount)\b",),
         "Real employers never charge you to give you a job."),
    Rule("job_bait", "Too-easy job offer", "job", 0.20, ("job_offer",),
         (r"\b(work from home|part[- ]time job|data entry job|typing job|like (and )?subscribe|earn (rs\.?|₹)?\s?\d[\d,]*\s*(per|a|/)\s*(day|week|hour)|offer letter)\b",),
         "High pay for simple remote work is a typical lure for job scams."),
    Rule("investment", "Guaranteed-returns / trading tip pitch", "investment", 0.40, ("investment",),
         (r"\b(guaranteed (returns?|profit)|double your money|100% (profit|returns?)|trading (tips|group|signals?)|crypto (invest\w*|trading)|stock tips?|insider tip|vip group|daily profit|risk[- ]free|returns? of \d+%)\b",),
         "Guaranteed or risk-free returns do not exist in real investing."),
    Rule("delivery", "Parcel / courier problem", "authority", 0.25, ("delivery_courier",),
         (r"\b(courier|parcel|package|delivery|india post|dtdc|bluedart|fedex|customs)\b[^.\n]{0,60}\b(held|pending|fee|failed|reschedule|customs|undelivered|address)\b",),
         "Fake 'parcel on hold' notices push you to pay a small fee or open a malicious link."),
    Rule("utility_threat", "Utility / telecom disconnection threat", "threat", 0.30, ("bank_kyc",),
         (r"\b(electricity|power|bijli|sim|mobile number)\b[^.\n]{0,40}\b(disconnect\w*|cut|deactivat\w*)\b[^.\n]{0,30}\b(tonight|today|hours?|immediately)\b",),
         "Utilities do not threaten same-day disconnection by message and ask you to call a personal number."),
    Rule("remote_access", "Asks you to install a remote-control app", "remote_access", 0.45, ("bank_kyc",),
         (r"\b(anydesk|teamviewer|quick ?support|rustdesk|screen ?share)\b", r"\bdownload\b[^.\n]{0,20}\b(app|apk)\b"),
         "Remote-access apps let a stranger see your screen and empty your bank account."),
    Rule("apk", "Asks you to install an APK file", "remote_access", 0.35, ("bank_kyc",),
         (r"\.apk\b", r"\binstall (this |the )?app\b"),
         "Apps installed from a link (not the Play Store) are a major route for banking malware."),
    Rule("romance", "Romance / overseas-stranger pattern", "romance", 0.20, ("romance",),
         (r"\bi am (a )?(widow|army (officer|doctor)|doctor|engineer)\b[^.\n]{0,25}\b(abroad|overseas|usa|uk|syria)\b", r"\bstuck at (the )?(airport|customs)\b",
          r"\b(my (dear|love|darling)|i (love|miss) you)\b[^.\n]{0,60}\b(gift|parcel|send|money)\b"),
         "A stranger building affection and then raising money or gifts is the core romance-scam pattern."),
]

_GRAMMAR = (
    r"\bdear (customer|user|sir/?madam|valued|account holder|beneficiary)\b", r"[!?]{3,}", r"\b(kindly|do the needful|revert back)\b",
    r"\s[,.!]\s*[a-z]",
)
_CRED = re.compile(r"\b(otp|one[- ]time password|upi pin|mpin|pin|cvv|cvc|password|passcode|card number|aadhaar number|pan number)\b", re.I)
_CRED_REQUEST = re.compile(
    r"\b(share|send|tell|give|provide|forward|read out|batao|bhejo|confirm|enter|reply with|submit|verify)\b[^.\n]{0,30}\b(otp|one[- ]time password|upi pin|mpin|pin|cvv|cvc|password|passcode|card number|aadhaar number|pan number)\b",
    re.I,
)
_NEGATION = re.compile(r"(not|never|don'?t|dont|nobody|no one|do not|ever)\s*(ever\s*)?$", re.I)
_WARNING = re.compile(r"\b(do not|don'?t|never|dont)\s+share\b[^.\n]{0,20}\b(otp|pin|password|cvv)\b", re.I)
_OTP_NOTICE = re.compile(r"\botp\b[^.\n]{0,15}\b(is|:)\s*\d{4,8}\b|\b\d{4,8}\b\s+is your\b[^.\n]{0,20}\botp\b", re.I)

_UPI_RE = re.compile(r"\b[a-zA-Z0-9._\-]{2,64}@[a-zA-Z]{2,20}\b(?!\.[a-zA-Z])")
_PHONE_RE = re.compile(r"(?<![\d])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakhs?|crore|k)\b)?|\b\d[\d,]*(?:\.\d+)?\s?(?:rupees|rs|lakhs?|crore|inr)\b", re.I)

_COMPILED = {r.id: [re.compile(p, re.I) for p in r.patterns] for r in RULES}
_GRAMMAR_C = [re.compile(p, re.I) for p in _GRAMMAR]

TYPE_LABELS = {
    "bank_kyc": "bank / KYC phishing", "digital_arrest": "'digital arrest' scam", "family_emergency": "family-emergency scam",
    "upi_payment": "UPI payment scam", "job_offer": "fake job offer", "lottery_prize": "lottery / prize scam",
    "investment": "investment scam", "delivery_courier": "fake courier notice", "romance": "romance scam",
    "other": "suspicious message", "likely_legit": "message with no scam patterns",
}


def extract_entities(text: str) -> dict[str, list[str]]:
    """Pull out phone numbers, UPI IDs, URLs and amounts."""
    upis = list(dict.fromkeys(_UPI_RE.findall(text)))
    urls = [u for u, _, _ in url_checker.extract_urls(text)]
    phones = list(dict.fromkeys(re.sub(r"\s+", " ", m.group(0)).strip() for m in _PHONE_RE.finditer(text)))
    amounts = list(dict.fromkeys(m.group(0).strip() for m in _AMOUNT_RE.finditer(text)))
    return {"upi_ids": upis, "urls": list(dict.fromkeys(urls)), "phone_numbers": phones, "amounts": amounts}


def _sig(rule: Rule, matched: str, extra: float = 0.0) -> Signal:
    return Signal(id=rule.id, name=rule.name, category="message", value=matched[:60], direction="suspicious",
                  weight=min(0.95, rule.weight + extra), detail=rule.detail)


def _pick_spans(cands: list[tuple[int, int, str, str, float]]) -> list[dict[str, Any]]:
    """Choose non-overlapping highlight spans, strongest first, returned in text order."""
    chosen: list[tuple[int, int, str, str, float]] = []
    for c in sorted(cands, key=lambda c: (-c[4], -(c[1] - c[0]))):
        if all(c[1] <= k[0] or c[0] >= k[1] for k in chosen):
            chosen.append(c)
    return [{"start": s, "end": e, "tactic": t, "signal_id": sid} for s, e, t, sid, _ in sorted(chosen)]


def analyze_message(text: str, sender_hint: str | None = None, llm_hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze message text. Returns signals, score inputs, scam type, entities and highlight spans."""
    signals: list[Signal] = []
    spans: list[tuple[int, int, str, str, float]] = []
    fired: set[str] = set()

    for rule in RULES:
        first: str | None = None
        count = 0
        for rx in _COMPILED[rule.id]:
            for m in rx.finditer(text):
                count += 1
                first = first or m.group(0)
                spans.append((m.start(), m.end(), rule.tactic, rule.id, rule.weight))
        if first:
            signals.append(_sig(rule, first, extra=0.05 if count >= 3 else 0.0))
            fired.add(rule.id)

    # Credential requests (ignoring 'never share your OTP' warnings)
    cred_first: str | None = None
    for m in _CRED_REQUEST.finditer(text):
        if _NEGATION.search(text[max(0, m.start() - 15): m.start()]):
            continue
        cred_first = cred_first or m.group(0)
        spans.append((m.start(), m.end(), "credentials", "otp_request", 0.55))
    if cred_first:
        signals.append(Signal(id="otp_request", name="Asks for OTP / PIN / password", category="message", value=cred_first[:60],
                              direction="suspicious", weight=0.55,
                              detail="No genuine bank, agency or friend needs your OTP, PIN or password; sharing it hands over your money."))
        fired.add("otp_request")

    # Tone mismatch: official body asking for private info over a chat/SMS
    hint = (sender_hint or "").lower()
    chatty = any(k in hint for k in ("whatsapp", "sms", "unknown", "dm", "telegram", "instagram"))
    if ("authority" in fired or "kyc_update" in fired) and (fired & {"otp_request", "kyc_update", "money_request", "upi_collect"}):
        signals.append(Signal(id="tone_mismatch", name="Official tone asking for private details by message", category="message",
                              value=sender_hint or "chat/SMS", direction="suspicious", weight=0.20 if chatty else 0.12,
                              detail="Real institutions do not collect private details or payments through unsolicited chat messages."))
        fired.add("tone_mismatch")

    # Grammar / format oddities (weak, single signal)
    g_first, g_count = None, 0
    for rx in _GRAMMAR_C:
        for m in rx.finditer(text):
            g_count += 1
            g_first = g_first or m.group(0)
            spans.append((m.start(), m.end(), "grammar", "format_oddities", 0.05))
    words = re.findall(r"[A-Za-z]{2,}", text)
    caps = sum(1 for w in words if w.isupper() and len(w) > 2)
    if len(words) >= 8 and caps / len(words) > 0.4:
        g_count += 1
        g_first = g_first or "ALL-CAPS text"
    if g_first:
        signals.append(Signal(id="format_oddities", name="Generic or oddly formatted wording", category="message", value=g_first[:40],
                              direction="suspicious", weight=0.06,
                              detail="Generic greetings, stray punctuation or shouting capitals are weak hints of mass-produced scam text."))
        fired.add("format_oddities")

    # URLs
    urls, url_signals = url_checker.analyze_urls(text)
    signals.extend(url_signals)
    for sig in url_signals:
        fired.add(sig.id)
    for u, s, e in urls:
        w = url_checker.url_risk(u)
        spans.append((s, e, "link", "url", max(0.05, w)))

    # Reassuring signals
    if _WARNING.search(text):
        signals.append(Signal(id="otp_warning", name="Contains a 'never share your OTP' warning", category="message", value=True,
                              direction="reassuring", weight=0.15,
                              detail="Genuine alerts typically warn you not to share codes; scams rarely include this."))
    if _OTP_NOTICE.search(text) and "otp_request" not in fired:
        signals.append(Signal(id="otp_notice", name="Looks like a one-time-code delivery notice", category="message", value=True,
                              direction="reassuring", weight=0.15,
                              detail="A bare code with no request to forward it is how real services deliver OTPs."))
    suspicious = [s for s in signals if s.direction == "suspicious" and s.id != "format_oddities"]
    if not suspicious and not urls:
        signals.append(Signal(id="no_risky_patterns", name="No scam patterns matched", category="message", value=True,
                              direction="reassuring", weight=0.20,
                              detail="No pressure, money, credential or impersonation patterns were found in the text."))

    # LLM booster (optional): can only add evidence, never remove any
    llm_conf = 0.0
    if llm_hint:
        c = llm_hint.get("confidence", 0)
        llm_conf = {"low": 0.4, "medium": 0.65, "high": 0.9}.get(str(c).lower(), 0.0) if not isinstance(c, (int, float)) else float(c)
        llm_conf = max(0.0, min(1.0, llm_conf))
        if llm_hint.get("scam_type") in SCAM_TYPES and llm_hint["scam_type"] not in ("likely_legit",) and llm_conf >= 0.6:
            signals.append(Signal(id="llm_assessment", name="AI reviewer also sees a scam pattern", category="message",
                                  value=str(llm_hint["scam_type"]), direction="suspicious", weight=round(min(0.3, 0.3 * llm_conf), 3),
                                  detail="A language model reviewing the wording independently judged it to follow a known scam pattern."))
            fired.add("llm_assessment")

    # Hard-signal floors (the LLM can never push the score below these)
    floor = 0.0
    urgent = bool(fired & {"urgency", "threat_block"})
    money = bool(fired & {"money_request", "upi_collect"})
    if "otp_request" in fired:
        floor = max(floor, 70)
    if money and urgent:
        floor = max(floor, 72)
    if "digital_arrest" in fired:
        floor = max(floor, 80 if fired & {"urgency", "secrecy", "money_request", "otp_request", "upi_collect"} else 55)
    if "remote_access" in fired:
        floor = max(floor, 70)
    if "family_emergency" in fired and money:
        floor = max(floor, 72)
    if "job_fee" in fired:
        floor = max(floor, 60)
    if "prize" in fired and (money or urls or "otp_request" in fired):
        floor = max(floor, 65)
    if "investment" in fired:
        floor = max(floor, 55)
    if fired & {"url_lookalike", "url_brand_mismatch", "url_punycode", "url_homoglyph", "url_at_trick", "url_ip_host"}:
        floor = max(floor, 72 if fired & {"kyc_update", "threat_block", "otp_request", "urgency"} else 60)
    hard = floor >= 55

    # LLM hint (optional): may only add weight, never lower
    extra_tactics: list[str] = []
    if llm_hint:
        extra_tactics = [str(t)[:60] for t in llm_hint.get("manipulation_tactics", [])][:6]

    score = fusion.message_score(signals, floor)
    entities = extract_entities(text)

    # Scam type
    type_scores: dict[str, float] = {}
    for rule in RULES:
        if rule.id in fired:
            for t in rule.types:
                type_scores[t] = type_scores.get(t, 0.0) + rule.weight
    if "otp_request" in fired:
        type_scores["bank_kyc"] = type_scores.get("bank_kyc", 0.0) + 0.3
    if entities["upi_ids"] and money:
        type_scores["upi_payment"] = type_scores.get("upi_payment", 0.0) + 0.3
    scam_type = "likely_legit"
    if score >= get_settings().risk_low_max or hard:
        scam_type = max(type_scores, key=type_scores.get) if type_scores else "other"
    if llm_hint and llm_hint.get("scam_type") in SCAM_TYPES and scam_type in ("other", "likely_legit") and score >= 35:
        scam_type = llm_hint["scam_type"]

    n_susp = len([s for s in suspicious])
    return {
        "signals": sorted(signals, key=lambda s: -s.weight),
        "score": score,
        "floor": floor,
        "hard": hard,
        "scam_type": scam_type,
        "entities": entities,
        "highlights": _pick_spans(spans),
        "tactics": sorted({t for _, _, t, _, _ in spans if t != "grammar"} | set(extra_tactics)),
        "confidence": fusion.message_confidence(n_susp, hard, len(text.strip())),
        "fired": sorted(fired),
    }
