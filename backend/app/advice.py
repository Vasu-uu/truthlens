"""Practical 'what to do next' steps, by modality, risk level and scam type."""
from __future__ import annotations

REPORT = "If money is lost, call 1930 (national cyber-fraud helpline) immediately and report at cybercrime.gov.in."

_BY_TYPE: dict[str, list[str]] = {
    "bank_kyc": [
        "Do not click the link or call any number in the message. Banks never ask for KYC or OTP over chat or SMS.",
        "Call your bank on the number printed on your card or on its official website.",
    ],
    "digital_arrest": [
        "There is no 'digital arrest' in India. Hang up; no agency demands money or video-call custody.",
        "Tell a family member right away; scammers rely on you staying isolated.",
    ],
    "family_emergency": [
        "Call your relative on their old, saved number before doing anything. Do not use the number in the message.",
        "Ask a question only the real person would know. Do not pay while you are unsure.",
    ],
    "upi_payment": [
        "Never approve a UPI 'collect' request or scan a QR code to receive money. Both take money out.",
        "Do not pay anyone 'to verify' something.",
    ],
    "job_offer": ["Do not pay any registration or training fee. Genuine employers never charge candidates."],
    "lottery_prize": ["You cannot win a contest you did not enter. Do not pay fees or share details to 'claim' it."],
    "investment": ["Guaranteed returns do not exist. Check the firm on the SEBI website before investing."],
    "delivery_courier": ["Track the parcel only on the courier's official app or site, not through the message link."],
    "romance": ["Never send money or gift-card codes to someone you have not met in person."],
}

_GENERIC_HIGH = [
    "Do not reply, pay, click links or share any OTP, PIN or password.",
    "Never share an OTP or PIN with anyone, even someone claiming to be from your bank.",
    "Block the sender and keep a screenshot as evidence.",
]
_GENERIC_MEDIUM = [
    "Pause and verify through a second, trusted channel (call the person or organisation on a number you already know).",
    "Do not click links or open attachments until you have verified.",
]
_GENERIC_LOW = [
    "Nothing alarming was found, but stay cautious with any request for money or codes.",
    "If something still feels off, verify through a number you already trust.",
]
_MEDIA = {
    "image": "Search for the image with a reverse-image tool (Google Lens, TinEye) to see where else it appears.",
    "audio": "Hang up and call the person back on their saved number. A cloned voice cannot answer a call you place yourself.",
}


def next_steps(modality: str, level: str, scam_type: str | None = None, extra_types: list[str] | None = None) -> list[str]:
    """Return a short, ordered, India-relevant action list."""
    steps: list[str] = []
    types = [scam_type] if scam_type else []
    types += extra_types or []
    if level != "low":
        for t in dict.fromkeys(types):
            steps += _BY_TYPE.get(t or "", [])
        if modality in _MEDIA:
            steps.append(_MEDIA[modality])
        if modality == "combined":
            steps += [_MEDIA["audio"], _MEDIA["image"]]
        steps += _GENERIC_HIGH if level == "high" else _GENERIC_MEDIUM
        if level == "high":
            steps.append(REPORT)
    else:
        steps += _GENERIC_LOW
        if modality in _MEDIA:
            steps.append(_MEDIA[modality])
    return list(dict.fromkeys(steps))[:7]
