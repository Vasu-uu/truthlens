"""Hit every TruthLens endpoint on a running backend and print a pass/fail table.

Usage:  python scripts/smoke_test.py [--url http://localhost:8000]
Needs `httpx` (installed with the backend requirements). Exit code 1 if anything fails.
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
import wave
import zlib
from pathlib import Path

import httpx

SAMPLES = Path(__file__).resolve().parents[1] / "backend" / "samples"
SCAM = "Mom I changed my number. I'm in trouble, send Rs 25,000 urgently to rahul@oksbi and don't tell papa."
LEGIT = "Hey, are we still meeting for lunch tomorrow at 1? Let me know if you want to change it."


def tiny_png(size: int = 96) -> bytes:
    """A small valid PNG (gradient) built without extra libraries."""
    raw = b""
    for y in range(size):
        raw += b"\x00" + b"".join(bytes(((x * 255) // size, (y * 255) // size, 128)) for x in range(size))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)  # noqa: E731
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def tone_wav(seconds: float = 3.0, sr: int = 16000) -> bytes:
    import math

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 150 * i / sr) * (1 if (i // 4000) % 2 == 0 else 0.3))) for i in range(int(seconds * sr))))
    return buf.getvalue()


def first(folder: str, exts: set[str]) -> Path | None:
    d = SAMPLES / folder
    return next((p for p in sorted(d.glob("*")) if p.suffix.lower() in exts), None) if d.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    base = ap.parse_args().url.rstrip("/")
    c = httpx.Client(base_url=base, timeout=180)
    rows: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            ok, note = fn()
        except Exception as exc:  # noqa: BLE001
            ok, note = False, f"{type(exc).__name__}: {str(exc)[:70]}"
        rows.append((name, bool(ok), note))

    def result_ok(r: httpx.Response, modality: str):
        j = r.json()
        good = r.status_code == 200 and j.get("modality") == modality and 0 <= j["risk_score"] <= 100 and j["signals"] and j["limitations"] and j["next_steps"]
        return good, f"{j.get('risk_score')} {j.get('risk_level')} ({j.get('confidence')} conf, {j.get('processing_ms')} ms)" if r.status_code == 200 else str(j)

    check("GET  /api/health", lambda: ((r := c.get("/api/health")).status_code == 200, f"device={r.json().get('device')}"))
    check("GET  /api/samples", lambda: ((r := c.get("/api/samples")).status_code == 200 and len(r.json()) > 0, f"{len(r.json())} samples"))
    check("POST /api/analyze/message (scam)", lambda: (lambda r: (result_ok(r, "message")[0] and r.json()["risk_level"] == "high", result_ok(r, "message")[1]))(c.post("/api/analyze/message", json={"text": SCAM})))
    check("POST /api/analyze/message (legit)", lambda: (lambda r: (result_ok(r, "message")[0] and r.json()["risk_level"] == "low", result_ok(r, "message")[1]))(c.post("/api/analyze/message", json={"text": LEGIT})))
    img = first("image/real", {".jpg", ".jpeg", ".png"})
    img_bytes, img_name = (img.read_bytes(), img.name) if img else (tiny_png(), "generated.png")
    check("POST /api/analyze/image", lambda: result_ok(c.post("/api/analyze/image", files={"file": (img_name, img_bytes)}), "image"))
    aud = first("audio/synthetic", {".wav", ".mp3", ".ogg"})
    aud_bytes, aud_name = (aud.read_bytes(), aud.name) if aud else (tone_wav(), "tone.wav")
    check("POST /api/analyze/audio", lambda: result_ok(c.post("/api/analyze/audio", files={"file": (aud_name, aud_bytes)}), "audio"))
    check("POST /api/analyze/combined", lambda: result_ok(c.post("/api/analyze/combined", data={"text": SCAM}, files={"audio": (aud_name, aud_bytes), "image": (img_name, img_bytes)}), "combined"))
    check("POST /api/analyze/sample/{id}", lambda: result_ok(c.post("/api/analyze/sample/msg-scam-son-in-trouble"), "message"))
    check("error: empty message -> 400", lambda: (lambda r: (r.status_code == 400 and r.json()["code"] == "empty_text", r.json().get("code")))(c.post("/api/analyze/message", json={"text": " "})))
    check("error: corrupt image -> 400", lambda: (lambda r: (r.status_code == 400 and r.json()["code"] == "invalid_image", r.json().get("code")))(c.post("/api/analyze/image", files={"file": ("x.jpg", b"not an image")})))
    check("error: corrupt audio -> 400", lambda: (lambda r: (r.status_code == 400 and r.json()["code"] == "invalid_audio", r.json().get("code")))(c.post("/api/analyze/audio", files={"file": ("x.mp3", b"not audio" * 40)})))
    check("error: oversize image -> 413", lambda: (lambda r: (r.status_code == 413, r.json().get("code")))(c.post("/api/analyze/image", files={"file": ("big.jpg", b"0" * (11 * 1024 * 1024))})))
    check("error: unknown sample -> 404", lambda: (lambda r: (r.status_code == 404, r.json().get("code")))(c.post("/api/analyze/sample/nope")))

    w = max(len(n) for n, _, _ in rows)
    print(f"\nTruthLens smoke test against {base}\n" + "-" * (w + 60))
    for name, ok, note in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{w}}  {note}")
    failed = [n for n, ok, _ in rows if not ok]
    print("-" * (w + 60) + f"\n{len(rows) - len(failed)}/{len(rows)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
