"""Audio analysis: learned anti-spoof classifier + weak, explainable spectral features."""
from __future__ import annotations

import logging
from typing import Any

import cv2
import librosa
import numpy as np

from app.schemas import Signal
from app.utils import model_loader
from app.utils.audio_io import MODEL_SR, NATIVE_SR, LoadedAudio
from app.utils.image_io import png_b64

log = logging.getLogger("truthlens.audio")

SYNTH_HINTS = ("fake", "spoof", "synthetic", "deepfake", "generated", "ai")
REAL_HINTS = ("real", "bonafide", "bona-fide", "genuine", "human", "authentic")
WINDOW_S, MAX_WINDOWS = 6.0, 10


def _pct(p: float) -> str:
    """Human wording for a probability that never claims certainty."""
    if p >= 0.99:
        return "over 99%"
    if p <= 0.01:
        return "under 1%"
    return f"about {p:.0%}"


def _sig(sid: str, name: str, value: Any, direction: str, weight: float, detail: str) -> Signal:
    return Signal(id=sid, name=name, category="audio", value=value, direction=direction, weight=round(weight, 3), detail=detail)  # type: ignore[arg-type]


def _synthetic_index(id2label: dict[int, str]) -> int:
    for i, lab in id2label.items():
        l = lab.lower()
        if any(h in l for h in SYNTH_HINTS) and not any(h in l for h in REAL_HINTS):
            return int(i)
    for i, lab in id2label.items():
        if any(h in lab.lower() for h in REAL_HINTS):
            return [int(j) for j in id2label if int(j) != int(i)][0]
    raise RuntimeError(f"Cannot tell which label means synthetic: {id2label}")


def _windows(y: np.ndarray) -> list[np.ndarray]:
    n = int(WINDOW_S * MODEL_SR)
    if y.size <= int(1.5 * n):
        return [y]
    wins = [y[i:i + n] for i in range(0, y.size - n // 4, n)]
    wins = [w for w in wins if w.size >= int(1.5 * MODEL_SR)] or [y]
    return wins[:MAX_WINDOWS]


def classify(y16: np.ndarray) -> tuple[float, float, int]:
    """Return (mean P(synthetic), std across windows, n_windows)."""
    import torch

    fe, model = model_loader.load_audio_model()
    dev = next(model.parameters()).device
    idx = _synthetic_index(model.config.id2label)
    ps: list[float] = []
    for w in _windows(y16):
        inp = fe(w, sampling_rate=MODEL_SR, return_tensors="pt")
        with torch.no_grad():
            logits = model(**{k: v.to(dev) for k, v in inp.items()}).logits
        ps.append(float(torch.softmax(logits, -1)[0, idx]))
    return float(np.mean(ps)), float(np.std(ps)), len(ps)


# ------------------------------------------------------------------ features
def _db(x: np.ndarray) -> np.ndarray:
    return 20 * np.log10(np.maximum(x, 1e-9))


def feature_signals(a: LoadedAudio) -> tuple[list[Signal], dict[str, float], list[str]]:
    """Weak spectral/prosodic signals. Returns (signals, stats, notes about checks that could not run)."""
    sigs: list[Signal] = []
    notes: list[str] = []
    y = a.y16
    hop = 256
    rms = librosa.feature.rms(y=y, frame_length=512, hop_length=hop)[0]
    rdb = _db(rms)
    p90, floor_db = float(np.percentile(rdb, 90)), float(np.percentile(rdb, 10))
    stats = {"noise_floor_db": floor_db, "speech_level_db": p90}

    # Room noise / unnaturally clean
    if floor_db < -65:
        sigs.append(_sig("too_clean", "Unnaturally clean background", f"{floor_db:.0f} dBFS", "suspicious", 0.12,
                         "The gaps between words are almost perfectly silent. Real rooms have a little background noise; generated audio often does not."))
    else:
        sigs.append(_sig("room_noise", "Natural background noise present", f"{floor_db:.0f} dBFS", "reassuring", 0.08,
                         "There is a believable level of background noise between words, as in a real recording."))

    # Pause regularity
    quiet = rdb < (p90 - 25)
    pauses, run = [], 0
    for q in quiet:
        if q:
            run += 1
        else:
            if run * hop / MODEL_SR >= 0.15:
                pauses.append(run * hop / MODEL_SR)
            run = 0
    if len(pauses) >= 4:
        cv = float(np.std(pauses) / (np.mean(pauses) + 1e-6))
        reg = cv < 0.25
        sigs.append(_sig("pause_regularity", "Pause rhythm", f"cv={cv:.2f} over {len(pauses)} pauses", "suspicious" if reg else "neutral",
                         0.10 if reg else 0.03,
                         "Pauses are almost evenly spaced, more machine-like than natural speech (weak evidence)."
                         if reg else "Pauses vary naturally in length."))
    else:
        notes.append("Pause-pattern check skipped: too few pauses in the recording.")

    # Pitch variation
    try:
        f0 = librosa.yin(y, fmin=70, fmax=400, sr=MODEL_SR, frame_length=1024, hop_length=hop)
        n = min(len(f0), len(rdb))
        flat = librosa.feature.spectral_flatness(y=y, n_fft=1024, hop_length=hop)[0][:n]
        voiced = (rdb[:n] > p90 - 20) & (flat < 0.2) & (f0[:n] > 75) & (f0[:n] < 395)
        if voiced.sum() >= 40:
            st = 12 * np.log2(f0[:n][voiced] / np.median(f0[:n][voiced]))
            spread = float((np.percentile(st, 75) - np.percentile(st, 25)) / 1.35)
            mono = spread < 1.0
            sigs.append(_sig("pitch_variation", "Pitch (F0) variation", f"{spread:.1f} semitones", "suspicious" if mono else "neutral",
                             0.12 if mono else 0.03,
                             "The voice pitch barely changes, which can indicate flat synthetic speech (or just a calm reader)."
                             if mono else "The pitch moves naturally as in expressive human speech."))
            stats["f0_spread_st"] = spread
        else:
            notes.append("Pitch check skipped: not enough clearly voiced speech.")
        sigs.append(_sig("spectral_flatness", "Spectral flatness", f"{float(np.mean(flat[voiced])) if voiced.any() else float(np.mean(flat)):.3f}",
                         "neutral", 0.03, "Measures how noise-like versus tonal the sound is. Informational only; it is not scored heavily."))
    except Exception as exc:  # noqa: BLE001
        notes.append("Pitch and spectral-flatness checks could not run.")
        log.warning("pitch failed: %s", type(exc).__name__)

    # Band limit
    try:
        S = np.abs(librosa.stft(a.y32, n_fft=2048, hop_length=1024)) ** 2
        S = S[:, S.sum(axis=0) > np.percentile(S.sum(axis=0), 30)]
        mdb = 10 * np.log10(np.maximum(S.mean(axis=1), 1e-14))
        freqs = np.linspace(0, NATIVE_SR / 2, len(mdb))
        ref = float(np.median(mdb[freqs > 15000]))
        above = np.where(mdb > ref + 12)[0]
        cutoff = float(freqs[above.max()]) if above.size else 0.0
        stats["cutoff_hz"] = cutoff
        if cutoff < 5000:
            sigs.append(_sig("band_limit", "Very narrow frequency range", f"{cutoff/1000:.1f} kHz", "neutral", 0.04,
                             "Little sound above ~5 kHz: typical of phone calls or heavy compression, which also makes detection less reliable."))
        elif cutoff < 9500:
            sigs.append(_sig("band_limit", "Frequency cut-off near 8 kHz", f"{cutoff/1000:.1f} kHz", "suspicious", 0.06,
                             "The audio stops at about 8 kHz. Some text-to-speech systems and voice-note codecs do this, so it is only a faint hint."))
        else:
            sigs.append(_sig("band_limit", "Wide frequency range", f"{cutoff/1000:.1f} kHz", "neutral", 0.03,
                             "The recording keeps high frequencies, consistent with a good-quality recording."))
    except Exception as exc:  # noqa: BLE001
        notes.append("Frequency cut-off check could not run.")
        log.warning("cutoff failed: %s", type(exc).__name__)

    # Clipping
    clip = float(np.mean(np.abs(a.y32) >= 0.99))
    if clip > 0.001:
        sigs.append(_sig("clipping", "Audio clipping", f"{clip*100:.2f}% of samples", "neutral", 0.03,
                         "Parts of the signal hit the maximum level, a common recording flaw (neutral)."))
    return sigs, stats, notes


# ------------------------------------------------------------------ artifacts
def spectrogram_png(y16: np.ndarray) -> str:
    """Mel spectrogram rendered as a base64 PNG."""
    m = librosa.feature.melspectrogram(y=y16, sr=MODEL_SR, n_fft=1024, hop_length=256, n_mels=96, fmax=8000)
    db = librosa.power_to_db(m, ref=np.max)
    g = np.uint8(255 * np.clip((db + 80) / 80, 0, 1))[::-1]
    w = min(900, max(300, g.shape[1]))
    g = cv2.resize(g, (w, 240), interpolation=cv2.INTER_AREA)
    return png_b64(cv2.cvtColor(cv2.applyColorMap(g, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB))


def waveform_peaks(y: np.ndarray, n: int = 200) -> list[float]:
    """Normalised peak envelope for drawing a waveform."""
    chunks = np.array_split(np.abs(y), n)
    p = np.array([c.max() if c.size else 0.0 for c in chunks])
    return [round(float(v), 3) for v in p / (p.max() + 1e-9)]


def model_signal(p: float, n_windows: int) -> Signal:
    """Signal describing the classifier output."""
    sus = p >= 0.5
    return _sig("synthetic_voice_model", "Synthetic-voice classifier estimate", round(p, 3), "suspicious" if sus else "reassuring",
                max(0.1, min(1.0, abs(p - 0.5) * 2)),
                f"The voice classifier puts the likelihood that this is synthetic or cloned speech at {_pct(p)}."
                if sus else f"The voice classifier puts the likelihood that this is synthetic or cloned speech at {_pct(p)}.")


def analyze(a: LoadedAudio) -> dict[str, Any]:
    """Run model + features + artifacts."""
    p, spread, nwin = classify(a.y16)
    sigs, stats, notes = feature_signals(a)
    artifacts = {"spectrogram_png_base64": spectrogram_png(a.y16), "waveform_peaks": waveform_peaks(a.y16),
                 "duration_s": round(a.duration_s, 2), "windows_analyzed": nwin, "model_probability_synthetic": round(p, 4)}
    return {"model_prob": p, "window_spread": spread, "n_windows": nwin, "signals": sigs, "stats": stats, "notes": notes, "artifacts": artifacts}
