"""Score fusion. Formulas are documented in docs/ARCHITECTURE.md.

Single modality (image/audio):  score = 100 * (0.6 * model_prob + 0.4 * signal_score)
Message:                        score = 100 * noisy_or(suspicious weights) * (1 - damp), then hard-signal floors
Combined:                       score = min(100, 0.6 * max + 0.4 * mean + cross_modal_bonus)
"""
from __future__ import annotations

from typing import Iterable, Literal

from app.config import get_settings
from app.schemas import Signal

Level = Literal["low", "medium", "high"]
Confidence = Literal["low", "medium", "high"]


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp x into [lo, hi]."""
    return max(lo, min(hi, x))


def risk_level(score: float) -> Level:
    """Map a 0-100 score to a level using configured thresholds (Low < 35, High > 65)."""
    s = get_settings()
    if score < s.risk_low_max:
        return "low"
    if score > s.risk_high_min:
        return "high"
    return "medium"


def noisy_or(weights: Iterable[float]) -> float:
    """Probabilistic OR of independent weights in [0,1]: 1 - prod(1 - w)."""
    p = 1.0
    for w in weights:
        p *= 1.0 - clamp(w, 0.0, 1.0)
    return 1.0 - p


def signal_score(signals: list[Signal]) -> float:
    """0-1 evidence score from signals: suspicious noisy-OR, damped by reassuring signals (max 25%)."""
    sus = noisy_or(s.weight for s in signals if s.direction == "suspicious")
    damp = min(0.25, 0.5 * sum(s.weight for s in signals if s.direction == "reassuring"))
    return clamp(sus * (1.0 - damp), 0.0, 1.0)


def fuse_single(model_prob: float, signals: list[Signal]) -> int:
    """Image/audio score: 100 * (0.6 * model_prob + 0.4 * signal_score), bounded to 0-100."""
    p = clamp(model_prob, 0.0, 1.0)
    return int(round(clamp(100 * (0.6 * p + 0.4 * signal_score(signals)))))


def message_score(signals: list[Signal], floor: float = 0.0) -> int:
    """Message score: rules-driven noisy-OR, raised to a hard-signal floor if one applies."""
    base = 100 * signal_score(signals)
    return int(round(clamp(max(base, floor))))


def fuse_combined(scores: dict[str, int], bonus: float = 0.0) -> int:
    """Max-biased aggregation: 0.6*max + 0.4*mean + bonus, capped at 100.

    One low-scoring modality can never pull a strongly suspicious one below
    0.6*max + 0.4*mean, and max itself keeps the verdict at least 60% of the worst.
    """
    if not scores:
        return 0
    vals = list(scores.values())
    return int(round(clamp(0.6 * max(vals) + 0.4 * (sum(vals) / len(vals)) + bonus)))


def message_confidence(n_suspicious: int, hard: bool, text_len: int) -> Confidence:
    """Confidence in a message verdict (not the risk itself)."""
    if text_len < 25:
        return "low"
    if hard or n_suspicious >= 3:
        return "high"
    if n_suspicious >= 1 or text_len >= 60:
        return "medium"
    return "low"


def model_confidence(prob: float, degraded: bool = False, conflict: bool = False) -> Confidence:
    """Confidence in an image/audio verdict from classifier certainty, input quality and agreement.

    Certainty: |p-0.5| > 0.35 high, > 0.15 medium, else low. Each of `degraded`
    (tiny / heavily compressed / very short input) and `conflict` (model and
    heuristics disagree) lowers the result by one step.
    """
    d = abs(prob - 0.5)
    level = 2 if d > 0.35 else 1 if d > 0.15 else 0
    level -= int(degraded) + int(conflict)
    return ("low", "medium", "high")[max(0, level)]  # type: ignore[return-value]


SCAM_STORY_TYPES = {"family_emergency", "upi_payment", "digital_arrest", "bank_kyc"}


def cross_modal_bonus(scores: dict[str, int], message_scam_type: str | None) -> tuple[float, str | None]:
    """Bonus (0-15) when modalities line up with a known scam story, plus a short reason.

    - image + audio + message all >= 50: +15 (coordinated impersonation)
    - any two of them >= 50 including a message of a known scam story: +10
    Never negative, so a weak modality cannot reduce a strong one.
    """
    hot = {m for m, v in scores.items() if v >= 50}
    story = message_scam_type in SCAM_STORY_TYPES
    if len(scores) >= 3 and len(hot) == 3:
        return 15.0, "image, voice and message all show warning signs together"
    if len(hot) >= 2 and "message" in hot and story:
        return 10.0, "the message follows a known scam script and is backed by suspicious media"
    return 0.0, None


def combined_confidence(confidences: dict[str, Confidence], scores: dict[str, int]) -> Confidence:
    """Confidence of the highest-scoring modality (the one driving the verdict)."""
    top = max(scores, key=lambda m: scores[m])
    return confidences[top]
