# TruthLens: Devfolio submission

**Title:** TruthLens: Deepfake & AI-Fraud Shield

**Tagline:** Check a suspicious photo, voice note or message in one place, and see the evidence, not just a verdict.

## Problem
Scams in India increasingly combine a cloned voice, an AI-made photo and an urgent UPI/OTP/KYC message ("I changed my number, I'm in trouble", "digital arrest", fake bank KYC). Victims, often students and elders, have no quick way to check any of it, and existing detectors give a bare "87% fake" with no reasoning, which is easy to distrust or over-trust.

## Solution
TruthLens accepts an **image**, a **voice note** (including WhatsApp `.opus`) and a **message**, separately or together. For each it returns a risk score and level, an honest **confidence**, the list of **measured signals** behind the score, a plain-language explanation written *only* from those signals, and practical next steps (call back on a saved number, never share OTP, report at 1930 / cybercrime.gov.in). In **Combined** mode it checks whether the pieces fit one scam story and says so.

## How it works
- **Image:** pretrained AI-image classifier + metadata (EXIF, embedded generator settings, C2PA claims) + Error Level Analysis + frequency checks, with a Grad-CAM heat map.
- **Voice:** pretrained anti-spoofing model over short windows + pitch, pause, noise and band-limit features + spectrogram.
- **Message:** an offline rule engine for Indian scam scripts plus a lexical URL checker (look-alike domains, shorteners, punycode); an optional LLM can add evidence but never lower a hard warning.
- **Fusion:** transparent formulas (documented), a cross-modal bonus only when the pattern matches a known story, and a separate confidence that drops for short, small, noisy or conflicting inputs.
- **Grounded explanations:** an LLM (optional) may only restate signals and must cite their ids; ungrounded or overconfident sentences are dropped, with a template fallback that needs no API key.
- **Privacy:** files are processed in memory and discarded; history keeps only verdict summaries in the browser.

## Tech stack
Python, FastAPI, PyTorch, Hugging Face Transformers, librosa, OpenCV, scikit-image, pytorch-grad-cam · React, Vite, TypeScript, Tailwind CSS · Chrome Manifest V3 extension · Docker Compose · pytest.

## Challenges
- **A model that ignored its input.** Our first audio detector returned identical outputs for different voices. We caught it by testing control inputs and swapped models instead of shipping a confident-looking guess.
- **Honest wording.** Making every probability, headline and explanation avoid certainty, including capping "100%" to "over 99%".
- **Privacy leaks in small places.** We found matched message phrases leaking into saved history and into LLM prompts, and removed them, with a regression test.
- **No ground truth.** We had no labelled deepfakes offline, so we built `scripts/evaluate.py` to measure on real data and refuse to invent numbers.

## What's next
A labelled evaluation set and calibrated thresholds; broader language support; screenshots and video; verified C2PA validation; GPU/ONNX speed-ups; stronger face-swap forensics; a WhatsApp Web helper.

## Honest status
Working end to end: three detectors, combined mode, grounded explanations, web app, extension, 63 backend tests passing. **Not yet measured:** accuracy on real-world deepfakes, and the audio model's false-positive rate on real speech. These are documented in `docs/LIMITATIONS.md`.
