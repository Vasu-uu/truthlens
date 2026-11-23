"""Audio detector and endpoint tests."""
import io
import shutil

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.detectors import audio_detector as det
from app.main import app
from app.schemas import AnalysisResult

client = TestClient(app)


def _speechlike(seconds=4.0, sr=16000, noise=0.003) -> bytes:
    """Deterministic voiced-ish signal with syllable gaps (not real speech)."""
    rng = np.random.default_rng(3)
    t = np.arange(int(seconds * sr)) / sr
    f0 = 120 + 25 * np.sin(2 * np.pi * 0.7 * t)
    ph = 2 * np.pi * np.cumsum(f0) / sr
    y = sum(np.sin(k * ph) / k for k in range(1, 8))
    y *= (np.sin(2 * np.pi * 2.5 * t) > -0.2).astype(float) * 0.2
    y += rng.normal(0, noise, y.size)
    b = io.BytesIO()
    sf.write(b, y.astype(np.float32), sr, format="WAV")
    return b.getvalue()


def test_synthetic_index_by_label():
    assert det._synthetic_index({0: "fake", 1: "real"}) == 0
    assert det._synthetic_index({0: "bonafide", 1: "spoof"}) == 1
    assert det._synthetic_index({0: "AIVoice", 1: "HumanVoice"}) == 0


def test_endpoint_wav_schema_and_artifacts():
    r = client.post("/api/analyze/audio", files={"file": ("a.wav", _speechlike(), "audio/wav")})
    assert r.status_code == 200, r.text
    res = AnalysisResult(**r.json())
    assert res.modality == "audio" and 0 <= res.risk_score <= 100
    assert "synthetic_voice_model" in {s.id for s in res.signals}
    assert res.artifacts["spectrogram_png_base64"] and len(res.artifacts["waveform_peaks"]) == 200
    assert any("Compression" in l for l in res.limitations) and res.next_steps


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_ogg_opus_and_mp3_decode(tmp_path):
    import subprocess
    wav = tmp_path / "a.wav"
    wav.write_bytes(_speechlike())
    for ext, codec in (("ogg", "libopus"), ("mp3", "libmp3lame"), ("m4a", "aac")):
        out = tmp_path / f"a.{ext}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", codec, str(out)], check=True)
        r = client.post("/api/analyze/audio", files={"file": (out.name, out.read_bytes(), "audio/x")})
        assert r.status_code == 200, (ext, r.text)


def test_short_audio_lowers_confidence():
    r = client.post("/api/analyze/audio", files={"file": ("s.wav", _speechlike(1.5), "audio/wav")}).json()
    assert r["confidence"] in ("low", "medium") and any("short" in l for l in r["limitations"])


def test_too_short_silent_corrupt_oversize():
    short = client.post("/api/analyze/audio", files={"file": ("s.wav", _speechlike(0.2), "audio/wav")})
    assert short.status_code == 400 and short.json()["code"] == "audio_too_short"
    b = io.BytesIO()
    sf.write(b, np.zeros(16000 * 2, dtype=np.float32), 16000, format="WAV")
    assert client.post("/api/analyze/audio", files={"file": ("z.wav", b.getvalue(), "audio/wav")}).json()["code"] == "audio_silent"
    bad = client.post("/api/analyze/audio", files={"file": ("x.mp3", b"definitely not audio" * 50, "audio/mpeg")})
    assert bad.status_code == 400 and bad.json()["code"] == "invalid_audio"
    big = client.post("/api/analyze/audio", files={"file": ("b.wav", b"0" * (16 * 1024 * 1024), "audio/wav")})
    assert big.status_code == 413 and big.json()["code"] == "file_too_large"


def test_long_audio_is_truncated_at_60s():
    from app.utils.audio_io import load_audio
    a = load_audio(_speechlike(75.0))
    assert a.truncated and a.duration_s <= 60.01
