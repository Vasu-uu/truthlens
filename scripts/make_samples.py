"""Build demo samples under backend/samples/ (idempotent).

Creates:
  * folder layout + README for adding real / AI images and real / synthetic audio
  * synthetic voice clips via an offline TTS engine (pyttsx3), if available
  * a few real public-domain test photos from scikit-image (as the 'real' image examples)
messages.json (scam / legit message samples) is checked in and left untouched.

Usage:  backend/.venv/Scripts/python scripts/make_samples.py
"""
from __future__ import annotations

from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[1] / "backend" / "samples"
DIRS = ["image/real", "image/ai", "audio/real", "audio/synthetic"]

README = """# TruthLens demo samples

Anything placed in these folders shows up in the app's Samples gallery automatically.
The folder name is only the sample's *source label*; it is never used to decide a verdict.

| Folder | Put here |
| --- | --- |
| `image/real` | Genuine photos you took or have the rights to use (JPG/PNG/WebP). |
| `image/ai` | AI-generated images you made yourself (Midjourney, SDXL, DALL-E, ...). **Not bundled**: we can't ship these reliably. |
| `audio/real` | Real voice recordings, ideally including a WhatsApp `.opus`/`.ogg` voice note. Use your own voice or someone who agreed. |
| `audio/synthetic` | Text-to-speech or cloned-voice clips. `scripts/make_samples.py` generates some with an offline TTS engine. |

`messages.json` holds the scam / genuine message samples. Add your own entries with
`id`, `title`, `expected` (`scam` or `legit`) and `text`.

Tips
* Keep clips under 60 s and images under 10 MB.
* For a fair demo include both a real and a fake of each kind, and *also* try compressed
  (WhatsApp-forwarded) versions: accuracy drops on compressed media, and that is worth showing.
* To measure accuracy on your own labelled files, see `scripts/evaluate.py`.
"""

LINES = {
    "tts_family_emergency": "Mom, it's me. I lost my phone and I am in trouble. Please send twenty five thousand rupees to this account right now, and don't tell dad.",
    "tts_bank_otp": "This is a call from your bank. Your account will be blocked today. Please share the O T P you just received to verify your K Y C.",
}


def make_tts() -> None:
    try:
        import pyttsx3
    except ImportError:
        print("pyttsx3 not installed: skipping synthetic audio")
        return
    out = SAMPLES / "audio" / "synthetic"
    try:
        engine = pyttsx3.init()
        for name, text in LINES.items():
            path = out / f"{name}.wav"
            if path.exists():
                print("exists", path.name)
                continue
            engine.save_to_file(text, str(path))
            engine.runAndWait()
            print("wrote", path.name)
        engine.stop()
    except Exception as exc:  # noqa: BLE001 - TTS engines vary by OS
        print(f"TTS failed ({type(exc).__name__}: {exc}). On Linux install espeak-ng; or add clips by hand.")


def make_real_photos() -> None:
    try:
        from PIL import Image
        from skimage import data
    except ImportError:
        print("scikit-image/Pillow missing: skipping example photos")
        return
    out = SAMPLES / "image" / "real"
    for name in ("astronaut", "coffee", "chelsea"):
        path = out / f"{name}.jpg"
        if not path.exists():
            Image.fromarray(getattr(data, name)()).save(path, quality=92)
            print("wrote", path.name)


def main() -> None:
    for d in DIRS:
        (SAMPLES / d).mkdir(parents=True, exist_ok=True)
    (SAMPLES / "README.md").write_text(README, encoding="utf-8")
    make_real_photos()
    make_tts()
    print("\nDone. Add real voice notes to audio/real and AI images to image/ai (see README.md).")


if __name__ == "__main__":
    main()
