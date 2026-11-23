"""POST /api/analyze/image."""
from __future__ import annotations

import time

from fastapi import APIRouter, File, UploadFile

from app import advice, explainer, fusion
from app.config import get_settings
from app.detectors import image_detector as det
from app.schemas import AnalysisResult
from app.utils import model_loader
from app.utils.image_io import load_image
from app.utils.uploads import read_limited

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

IMAGE_LIMITATIONS = [
    "AI-image detectors are imperfect: new generators can evade them, and results on unfamiliar styles are less reliable.",
    "Real photos that were heavily edited, filtered, upscaled or compressed can be flagged by mistake.",
    "Missing metadata is common for genuine images shared through social apps, so it is only a weak hint.",
    "ELA and frequency checks are weak, uncalibrated indicators and cannot prove an image is real or fake.",
    "This is a guide, not a legal or forensic verdict.",
]


def run_image(data: bytes) -> AnalysisResult:
    """Full image pipeline on raw bytes."""
    t0 = time.perf_counter()
    li = load_image(data)
    out = det.analyze(li)
    p, forensic = out["model_prob"], out["forensic_signals"]
    score = max(fusion.fuse_single(p, forensic), int(out["floor"]))
    score = min(100, score)
    level = fusion.risk_level(score)
    signals = sorted([det.model_signal(p)] + forensic, key=lambda s: -s.weight)
    strong_real = any(s.id == "camera_make_model" for s in forensic)
    conflict = (p > 0.6 and strong_real) or (p < 0.4 and out["floor"] > 0)
    degraded = min(li.width, li.height) < 256
    conf = fusion.model_confidence(p, degraded=degraded, conflict=conflict)
    if out["floor"] >= 85:
        conf = "high" if conf != "low" else "medium"
    ex = explainer.explain("image", score, level, signals)
    limits = list(IMAGE_LIMITATIONS) + out["notes"]
    if degraded:
        limits.insert(0, "This image is small, so the verdict is less reliable.")
    s = get_settings()
    return AnalysisResult(
        modality="image", risk_score=score, risk_level=level, confidence=conf, headline=ex["headline"],
        signals=signals, explanation=ex["explanation"], next_steps=advice.next_steps("image", level),
        artifacts={**out["artifacts"], "image_format": li.fmt, "image_size": [li.width, li.height], "explanation_source": ex["source"],
                   "model_probability_ai": round(p, 4)},
        limitations=limits, processing_ms=int((time.perf_counter() - t0) * 1000),
        model_versions={"image_model": s.image_model_id, "device": model_loader.get_device()},
    )


@router.post("/image", response_model=AnalysisResult)
async def analyze_image(file: UploadFile = File(...)) -> AnalysisResult:
    """Analyze an uploaded image for AI generation or manipulation."""
    data = await read_limited(file, get_settings().max_image_mb, "image")
    return run_image(data)
