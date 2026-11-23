"""Audio decoding: any common format -> mono float32 at 32 kHz (and 16 kHz for models)."""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np
from scipy.signal import resample_poly

from app.config import get_settings
from app.main_errors import ApiError

NATIVE_SR = 32000
MODEL_SR = 16000


@dataclass
class LoadedAudio:
    """Decoded audio ready for analysis."""

    y32: np.ndarray       # mono @ 32 kHz (keeps band-limit information)
    y16: np.ndarray       # mono @ 16 kHz (model input)
    duration_s: float
    truncated: bool


def _decode_ffmpeg(data: bytes, max_s: int) -> np.ndarray | None:
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    fd, path = tempfile.mkstemp(suffix=".bin", prefix="tl_audio_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        proc = subprocess.run(
            [exe, "-nostdin", "-v", "error", "-t", str(max_s + 1), "-i", path, "-vn", "-ac", "1", "-ar", str(NATIVE_SR), "-f", "f32le", "pipe:1"],
            capture_output=True, timeout=40,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        return np.frombuffer(proc.stdout, dtype=np.float32).copy()
    except (subprocess.TimeoutExpired, OSError):
        return None
    finally:
        try:
            os.remove(path)  # uploads never persist
        except OSError:
            pass


def _decode_soundfile(data: bytes, max_s: int) -> np.ndarray | None:
    try:
        import soundfile as sf

        y, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True, frames=-1)
        y = y.mean(axis=1)[: int(sr * (max_s + 1))]
        if sr != NATIVE_SR:
            from math import gcd

            g = gcd(sr, NATIVE_SR)
            y = resample_poly(y, NATIVE_SR // g, sr // g).astype(np.float32)
        return y
    except Exception:  # noqa: BLE001
        return None


def load_audio(data: bytes) -> LoadedAudio:
    """Decode bytes. Raises ApiError for undecodable, too-short or silent audio."""
    max_s = get_settings().max_audio_seconds
    y = _decode_ffmpeg(data, max_s)
    if y is None:
        y = _decode_soundfile(data, max_s)
    if y is None or y.size == 0:
        raise ApiError(400, "invalid_audio", "This file could not be read as audio (supported: WAV, MP3, M4A, OGG, OPUS).")
    truncated = y.size > max_s * NATIVE_SR
    y = y[: max_s * NATIVE_SR]
    dur = y.size / NATIVE_SR
    if dur < 0.5:
        raise ApiError(400, "audio_too_short", "The recording is shorter than half a second.")
    if float(np.sqrt(np.mean(y ** 2))) < 1e-4:
        raise ApiError(400, "audio_silent", "The recording is silent, so there is nothing to analyse.")
    y16 = resample_poly(y, 1, 2).astype(np.float32)
    return LoadedAudio(y32=y, y16=y16, duration_s=dur, truncated=truncated)
