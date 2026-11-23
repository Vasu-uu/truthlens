# Limitations

TruthLens reports *likelihoods from measurable signals*. It is an aid for everyday safety decisions, **not** a legal, forensic or journalistic verdict.

## Known gaps in what we have tested
- **No accuracy has been measured.** The repository contains no labelled benchmark, and we report no accuracy figures. `scripts/evaluate.py` computes accuracy, precision, recall and a confusion matrix on files *you* provide.
- **The audio model has not been tested on real human speech.** We could only verify that it flags two Windows text-to-speech voices as synthetic. How often it wrongly flags real voices (WhatsApp notes, phone calls) is unknown.
- **No AI-generated image has been run through the image model** in our tests; image results were checked on real photos and on synthetic metadata cases only.
- The scam-message rules were written and tuned against the examples in this repo. They are not a measured detector.
- The Chrome extension's browser integration (menus, side panel) was not exercised in a real Chrome; its API logic was tested against the live backend.
- Docker files are untested on the build machine (no Docker installed).

## Images
- New generators can evade AI-image detectors, and detectors can fail on styles they were not trained on.
- Real photos that were heavily edited, filtered, upscaled or recompressed may be flagged.
- Missing EXIF is only a weak hint: social apps strip it from genuine images.
- Error Level Analysis and the frequency checks are uncalibrated, weak indicators.
- Metadata (EXIF, PNG text, C2PA claims) can be forged or stripped. A C2PA claim is detected, **not cryptographically verified**.
- Face-swap artefacts are not examined by dedicated face forensics; the face check only counts faces.

## Voice
- Compression (WhatsApp, phone calls, MP3) removes traces detectors rely on; accuracy drops.
- Short (<3 s) or noisy clips are unreliable; confidence is lowered for them.
- Modern voice-cloning systems can evade detection, and some real voices (monotone, heavily processed) can be flagged.
- Pitch, pause and band-limit features are weak hints.
- With the specified formula `0.6 × model + 0.4 × signals`, an uncorroborated classifier verdict tops out around 60-65, so even a near-certain model result can land in "Medium". This is intentional caution, and it is visible in the score.

## Messages
- Rule-based: novel or well-written scams may score low; genuine but alarming alerts may score higher.
- Hindi/Malayalam support is a small transliterated keyword list, not language understanding.
- Links are judged by their text only, never visited, so a clean-looking link is not proof of safety.
- The optional LLM can add evidence but can never lower a hard warning (OTP request, money + urgency, etc.).

## General
- Results are probabilistic. We avoid wording like "100% fake / real" on purpose.
- Device speed: on CPU an image takes about 2 s and a voice clip a few seconds once models are loaded; the first request after a cold start is much slower unless warm-up has finished.
- If an input is clearly high-stakes (money, safety, legal), verify through a trusted channel and report fraud at **1930** or **cybercrime.gov.in**.
