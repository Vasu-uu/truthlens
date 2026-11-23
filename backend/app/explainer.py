"""Grounded explanations. Every sentence must trace back to signal ids.

`explain()` uses the configured LLM when available; its output is filtered by
`ground_filter` (every sentence must cite real signal ids) and an overclaim
filter, and falls back to the deterministic template on any failure.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app import llm
from app.detectors.message_detector import TYPE_LABELS
from app.schemas import Signal


def ground_filter(items: list[dict[str, Any]], signals: list[Signal]) -> list[dict[str, Any]]:
    """Keep only sentences that cite at least one real signal id.

    items: [{"text": str, "signal_ids": [str, ...]}]. Sentences citing no id,
    or only ids absent from the signal list, are dropped.
    """
    valid = {s.id for s in signals}
    kept: list[dict[str, Any]] = []
    for it in items:
        ids = [i for i in it.get("signal_ids", []) if i in valid]
        text = str(it.get("text", "")).strip()
        if text and ids:
            kept.append({"text": text, "signal_ids": ids})
    return kept


def _headline(modality: str, level: str, scam_type: str | None) -> str:
    if modality == "combined":
        return {
            "high": "High likelihood this situation is a scam or impersonation attempt",
            "medium": "Some warning signs across what you submitted: verify before acting",
            "low": "No strong warning signs found across what you submitted",
        }[level]
    noun = {"image": "image", "audio": "voice recording", "message": "message", "combined": "set of items"}[modality]
    if modality == "message" and scam_type and scam_type not in ("other", "likely_legit") and level != "low":
        label = TYPE_LABELS.get(scam_type, "scam")
        return {"high": f"High likelihood of a {label}", "medium": f"Possible {label}: verify before acting"}[level]
    return {
        "high": f"High likelihood this {noun} is fake or fraudulent",
        "medium": f"Some warning signs in this {noun}: verify before trusting it",
        "low": f"No strong warning signs found in this {noun}",
    }[level]


def template_explanation(modality: str, score: int, level: str, signals: list[Signal], scam_type: str | None = None) -> dict[str, Any]:
    """Deterministic explanation built only from the highest-weight signals."""
    sus = sorted([s for s in signals if s.direction == "suspicious"], key=lambda s: -s.weight)
    good = sorted([s for s in signals if s.direction == "reassuring"], key=lambda s: -s.weight)
    items: list[dict[str, Any]] = []
    if level == "low":
        opener = "TruthLens did not find strong evidence of a problem."
    elif level == "medium":
        opener = "TruthLens found some warning signs, but not enough to be sure."
    else:
        opener = "TruthLens found several strong warning signs."
    if sus:
        items.append({"text": opener, "signal_ids": [sus[0].id]})
    elif good:
        items.append({"text": opener, "signal_ids": [good[0].id]})
    for s in sus[:3]:
        items.append({"text": s.detail, "signal_ids": [s.id]})
    if good and level != "high":
        items.append({"text": "On the reassuring side: " + good[0].detail[0].lower() + good[0].detail[1:], "signal_ids": [good[0].id]})
    items = [i for i in items if i["text"]][:6]
    caveat = "This is a likelihood based on measurable patterns, not proof."
    text = " ".join(i["text"] for i in items)
    text = f"{text} {caveat}" if text else caveat
    return {
        "headline": _headline(modality, level, scam_type),
        "explanation": text,
        "used_signal_ids": sorted({i for it in items for i in it["signal_ids"]}),
        "source": "template",
    }


_OVERCLAIM = re.compile(r"(100\s?%|definitely|certainly|guaranteed|absolutely|undoubtedly|proves?|is (a )?(fake|real))", re.I)

_SYSTEM = (
    "You write short safety explanations for non-technical people in India (students, elders). "
    "You are given ONLY a structured list of signals measured by a detector. "
    "Rules: (1) If a fact is not in the signal list, do not state it. (2) Never say something is certainly fake or real; "
    "use words like 'likelihood' and 'warning signs'. (3) Write 3-6 short plain sentences, no jargon. "
    "(4) Every sentence must cite the ids of the signals it relies on. "
    'Reply with JSON only: {"headline": str (max 12 words), "sentences": [{"text": str, "signal_ids": [str]}]}'
)


def llm_explanation(modality: str, score: int, level: str, signals: list[Signal], scam_type: str | None) -> dict[str, Any] | None:
    """LLM-written explanation, grounded and overclaim-filtered. None if unusable."""
    client = llm.get_client()
    if not client.enabled:
        return None
    top = sorted(signals, key=lambda s: -s.weight)[:12]
    payload = {
        "modality": modality, "risk_score": score, "risk_level": level, "scam_type": scam_type,
        # `value` is omitted for message/url signals: it holds matched fragments of the user's text, which must not leave the server.
        "signals": [{"id": s.id, "name": s.name, "direction": s.direction, "weight": s.weight,
                     "value": None if s.category in ("message", "url") else s.value, "detail": s.detail} for s in top],
    }
    out = client.complete_json(_SYSTEM, json.dumps(payload, ensure_ascii=False))
    if not out or not isinstance(out.get("sentences"), list):
        return None
    items = [it for it in out["sentences"] if isinstance(it, dict)]
    kept = [it for it in ground_filter(items, top) if not _OVERCLAIM.search(it["text"])]
    if len(kept) < 2:
        return None
    head = str(out.get("headline", "")).strip()
    if not head or len(head) > 120 or _OVERCLAIM.search(head):
        head = _headline(modality, level, scam_type)
    text = " ".join(it["text"] for it in kept[:6]) + " This is a likelihood based on measurable patterns, not proof."
    return {"headline": head, "explanation": text, "used_signal_ids": sorted({i for it in kept for i in it["signal_ids"]}), "source": "llm"}


def explain(modality: str, score: int, level: str, signals: list[Signal], scam_type: str | None = None) -> dict[str, Any]:
    """Headline + explanation. Uses the LLM when configured and grounded; otherwise the template."""
    try:
        res = llm_explanation(modality, score, level, signals, scam_type)
    except Exception:  # noqa: BLE001
        res = None
    return res or template_explanation(modality, score, level, signals, scam_type)
