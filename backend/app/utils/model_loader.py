"""Lazy, cached loading of Hugging Face models with device selection."""
from __future__ import annotations

import threading
from typing import Any

from app.config import get_settings

_lock = threading.Lock()
_cache: dict[str, Any] = {}
_errors: dict[str, str] = {}


def get_device() -> str:
    """Resolve the compute device: cuda if requested/available and usable, else cpu."""
    want = get_settings().device.lower()
    if want == "cpu":
        return "cpu"
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # pragma: no cover - torch missing
        pass
    return "cpu"


def load_image_model() -> tuple[Any, Any]:
    """Return (processor, model) for the image detector, cached."""
    return _load("image", get_settings().image_model_id, "image")


def load_audio_model() -> tuple[Any, Any]:
    """Return (feature_extractor, model) for the audio detector, cached."""
    return _load("audio", get_settings().audio_model_id, "audio")


def _load(key: str, model_id: str, kind: str) -> tuple[Any, Any]:
    with _lock:
        if key in _cache and _cache[key][0] == model_id:
            return _cache[key][1], _cache[key][2]
        try:
            import torch  # noqa: F401
            from transformers import (
                AutoFeatureExtractor,
                AutoImageProcessor,
                AutoModelForAudioClassification,
                AutoModelForImageClassification,
            )

            if kind == "image":
                proc = AutoImageProcessor.from_pretrained(model_id)
                model = AutoModelForImageClassification.from_pretrained(model_id)
            else:
                proc = AutoFeatureExtractor.from_pretrained(model_id)
                model = AutoModelForAudioClassification.from_pretrained(model_id)
            model.eval().to(get_device())
            _cache[key] = (model_id, proc, model)
            _errors.pop(key, None)
            return proc, model
        except Exception as exc:
            _errors[key] = f"{type(exc).__name__}: {exc}"[:300]
            raise


def status() -> dict[str, dict[str, Any]]:
    """Report which models are loaded / failed, without triggering a load."""
    s = get_settings()
    out: dict[str, dict[str, Any]] = {}
    for key, mid in (("image", s.image_model_id), ("audio", s.audio_model_id)):
        out[key] = {
            "model_id": mid,
            "loaded": key in _cache and _cache[key][0] == mid,
            "error": _errors.get(key),
        }
    return out
