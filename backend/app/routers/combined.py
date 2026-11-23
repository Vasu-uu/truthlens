"""POST /api/analyze/combined: fuse image + audio + message into one verdict."""
from __future__ import annotations

import time

from fastapi import APIRouter, File, Form, UploadFile

from app import advice, explainer, fusion
from app.config import get_settings
from app.main_errors import ApiError
from app.routers.audio import run_audio
from app.routers.image import run_image
from app.routers.message import run_message
from app.schemas import AnalysisResult, Signal
from app.utils.uploads import read_limited

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


def fuse_results(parts: dict[str, AnalysisResult], t0: float) -> AnalysisResult:
    """Merge per-modality results into one combined result."""
    scores = {m: r.risk_score for m, r in parts.items()}
    stype = parts["message"].artifacts.get("scam_type") if "message" in parts else None
    bonus, reason = fusion.cross_modal_bonus(scores, stype)
    score = fusion.fuse_combined(scores, bonus)
    level = fusion.risk_level(score)
    signals: list[Signal] = []
    if reason:
        signals.append(Signal(id="coordinated_impersonation", name="Coordinated impersonation pattern", category="cross-modal",
                              value=len(scores), direction="suspicious", weight=round(min(0.9, 0.4 + bonus / 30), 3),
                              detail=f"Taken together, {reason}, which is how family-emergency and impersonation scams are built."))
    for r in parts.values():
        signals += r.signals
    signals.sort(key=lambda s: -s.weight)
    conf = fusion.combined_confidence({m: r.confidence for m, r in parts.items()}, scores)
    ex = explainer.explain("combined", score, level, signals, stype)
    limits = list(dict.fromkeys(l for r in parts.values() for l in r.limitations))
    limits.append("The combined score is a max-weighted blend of each check plus a bonus when the pattern matches a known scam story; it is not a probability.")
    return AnalysisResult(
        modality="combined", risk_score=score, risk_level=level, confidence=conf, headline=ex["headline"], signals=signals,
        explanation=ex["explanation"], next_steps=advice.next_steps("combined", level, stype),
        artifacts={
            "per_modality": [{"modality": m, "risk_score": r.risk_score, "risk_level": r.risk_level, "confidence": r.confidence,
                              "headline": r.headline} for m, r in parts.items()],
            "cross_modal_bonus": bonus, "cross_modal_reason": reason,
            "parts": {m: {"artifacts": r.artifacts, "explanation": r.explanation} for m, r in parts.items()},
            "scam_type": stype, "explanation_source": ex["source"],
        },
        limitations=limits, processing_ms=int((time.perf_counter() - t0) * 1000),
        model_versions={k: v for r in parts.values() for k, v in r.model_versions.items()},
    )


@router.post("/combined", response_model=AnalysisResult)
async def analyze_combined(image: UploadFile | None = File(None), audio: UploadFile | None = File(None),
                           text: str | None = Form(None)) -> AnalysisResult:
    """Analyze any combination of image, audio and message text as one situation."""
    t0 = time.perf_counter()
    s = get_settings()
    img = await read_limited(image, s.max_image_mb, "image") if image and image.filename else None
    aud = await read_limited(audio, s.max_audio_mb, "audio") if audio and audio.filename else None
    txt = (text or "").strip() or None
    if not (img or aud or txt):
        raise ApiError(400, "no_input", "Provide at least one of: image, audio, or message text.")
    parts: dict[str, AnalysisResult] = {}
    if img:
        parts["image"] = run_image(img)
    if aud:
        parts["audio"] = run_audio(aud)
    if txt:
        parts["message"] = run_message(txt)
    return fuse_results(parts, t0)
