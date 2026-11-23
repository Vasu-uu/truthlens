"""POST /api/analyze/audio."""
from __future__ import annotations

import time

from fastapi import APIRouter, File, UploadFile

from app import advice, explainer, fusion
from app.config import get_settings
from app.detectors import audio_detector as det
from app.schemas import AnalysisResult
from app.utils import model_loader
from app.utils.audio_io import load_audio
from app.utils.uploads import read_limited

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

AUDIO_LIMITATIONS = [
    "Compression (WhatsApp voice notes, phone calls, MP3) removes the traces detectors rely on, so accuracy drops on such audio.",
    "New voice-cloning systems can evade detectors, and some real voices (monotone, heavily processed) are flagged by mistake.",
    "Short clips (under ~3 seconds) and noisy recordings give much less reliable results.",
    "Spectral features (pitch, pauses, band limit) are weak hints and cannot prove a voice is real or fake.",
    "Only the first 60 seconds are analysed. This is a guide, not a legal or forensic verdict.",
]


def run_audio(data: bytes) -> AnalysisResult:
    """Full audio pipeline on raw bytes."""
    t0 = time.perf_counter()
    a = load_audio(data)
    out = det.analyze(a)
    p = out["model_prob"]
    score = fusion.fuse_single(p, out["signals"])
    level = fusion.risk_level(score)
    signals = sorted([det.model_signal(p, out["n_windows"])] + out["signals"], key=lambda s: -s.weight)
    noisy = out["stats"].get("noise_floor_db", -90) > -35
    short = a.duration_s < 3
    degraded = short or noisy
    conflict = out["window_spread"] > 0.25
    conf = fusion.model_confidence(p, degraded=degraded, conflict=conflict)
    limits = list(AUDIO_LIMITATIONS) + out["notes"]
    if short:
        limits.insert(0, "This recording is very short, so the verdict is less reliable.")
    if noisy:
        limits.insert(0, "The recording is very noisy, so the verdict is less reliable.")
    if a.truncated:
        limits.append("The recording was longer than 60 seconds; only the first 60 seconds were analysed.")
    if conflict:
        limits.append("Different parts of the recording gave quite different results.")
    ex = explainer.explain("audio", score, level, signals)
    s = get_settings()
    return AnalysisResult(
        modality="audio", risk_score=score, risk_level=level, confidence=conf, headline=ex["headline"], signals=signals,
        explanation=ex["explanation"], next_steps=advice.next_steps("audio", level),
        artifacts={**out["artifacts"], "explanation_source": ex["source"]}, limitations=limits,
        processing_ms=int((time.perf_counter() - t0) * 1000),
        model_versions={"audio_model": s.audio_model_id, "device": model_loader.get_device()},
    )


@router.post("/audio", response_model=AnalysisResult)
async def analyze_audio(file: UploadFile = File(...)) -> AnalysisResult:
    """Analyze an uploaded voice recording for synthetic or cloned speech."""
    data = await read_limited(file, get_settings().max_audio_mb, "audio")
    return run_audio(data)
