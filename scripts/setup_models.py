"""Pre-download and verify all TruthLens models; print sizes.

Usage (from repo root):  backend/.venv/Scripts/python scripts/setup_models.py
Tries the configured model first, then the documented fallback candidates, and
prints which one worked so you can pin it in .env and docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402

IMAGE_CANDIDATES = [
    "umm-maybe/AI-image-detector",
    "Organika/sdxl-detector",
    "prithivMLmods/Deep-Fake-Detector-Model",
]
AUDIO_CANDIDATES = [
    "mo-thecreator/Deepfake-audio-detection",
    "Hemgg/Deepfake-audio-detection",
    "MelodyMachine/Deepfake-audio-detection-V2",  # loads, but returned constant logits on speech in our checks
]


def _size_mb(model) -> float:
    return sum(p.numel() * p.element_size() for p in model.parameters()) / 1e6


def try_model(kind: str, model_id: str) -> bool:
    """Download + load one model; print labels and size. Return success."""
    from transformers import (
        AutoFeatureExtractor,
        AutoImageProcessor,
        AutoModelForAudioClassification,
        AutoModelForImageClassification,
    )

    t0 = time.time()
    try:
        if kind == "image":
            AutoImageProcessor.from_pretrained(model_id)
            model = AutoModelForImageClassification.from_pretrained(model_id)
        else:
            AutoFeatureExtractor.from_pretrained(model_id)
            model = AutoModelForAudioClassification.from_pretrained(model_id)
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] {model_id}: {type(exc).__name__}: {str(exc)[:160]}")
        return False
    print(f"  [ OK ] {model_id}  {_size_mb(model):.0f} MB params  labels={model.config.id2label}  ({time.time()-t0:.1f}s)")
    return True


def main() -> int:
    s = get_settings()
    ok_all = True
    for kind, configured, cands in (
        ("image", s.image_model_id, IMAGE_CANDIDATES),
        ("audio", s.audio_model_id, AUDIO_CANDIDATES),
    ):
        print(f"\n== {kind} model ==")
        order = [configured] + [c for c in cands if c != configured]
        chosen = None
        for mid in order:
            if try_model(kind, mid):
                chosen = mid
                break
        if chosen:
            print(f"  -> use {kind.upper()}_MODEL_ID={chosen}")
        else:
            ok_all = False
            print(f"  -> no {kind} model could be loaded")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
