# Architecture

```
Browser app (React)  ──┐                      ┌── image_detector ── classifier + EXIF/C2PA + ELA + frequency + faces + Grad-CAM
Chrome extension     ──┼──►  FastAPI  ──►  ───┼── audio_detector ── anti-spoof model + spectral/prosody features + spectrogram
                       │   /api/analyze/*     └── message_detector ─ rule engine + URL checker (+ optional LLM)
                       │                                   │
                       │                       signals ──► fusion ──► explainer (LLM grounded / template) + advice
                       └────────────────────────────────── AnalysisResult JSON
```

Every endpoint returns the same `AnalysisResult` (see `backend/app/schemas.py`): score, level, confidence, headline, **signals**, explanation, next steps, artifacts, limitations, timing and model versions.

## Models (verified to load at build time)

| Role | Model id | Notes |
| --- | --- | --- |
| Image: AI-generated vs real | `umm-maybe/AI-image-detector` (default) | Swin transformer, labels `artificial` / `human`. Chosen first because it loaded and supports Grad-CAM. Alternatives that the setup script also tries: `Organika/sdxl-detector`, `prithivMLmods/Deep-Fake-Detector-Model`. |
| Audio: synthetic vs real | `mo-thecreator/Deepfake-audio-detection` (default) | wav2vec2-based, ~95M parameters, labels `fake` / `real`. |

**Why the audio default is not the brief's first candidate.** `MelodyMachine/Deepfake-audio-detection-V2` loads fine, but in our check it produced *identical logits* (`[-5.74, 5.25]`, i.e. "real" with ~100% certainty) for two different Windows TTS voices and for one of them with added noise. A detector that ignores its input is unusable, so we switched. Of the alternatives we tried (`mo-thecreator`, `Hemgg`, `Vansh180`, `Om-Parab/distilhubert…`), `mo-thecreator` and `Hemgg` flagged the TTS clips as synthetic. We chose `mo-thecreator`. This only shows sensitivity to TTS: its false-positive rate on real speech is **unmeasured** (see LIMITATIONS). Models are configurable via `IMAGE_MODEL_ID` / `AUDIO_MODEL_ID`; labels are mapped by name, not index.

Hardware: developed and tested on CPU (the dev machine's GPU is a 2 GB GTX 1050; PyTorch CPU build installed). `DEVICE=auto` uses CUDA when available.

## Scoring

Thresholds (configurable): **Low < 35, Medium 35-65, High > 65**.

- **Image / audio:** `score = round(100 × (0.6 × P_model + 0.4 × S))`, where `P_model` is the classifier's probability and `S` is the evidence score from the forensic/feature signals only (not counting the model's own signal, to avoid double counting). Strong embedded metadata (generator name in EXIF, SD parameters in PNG text, a C2PA "trained algorithmic media" claim) sets a floor (85-90) because such claims are explicit.
- **Evidence score `S`:** `S = noisy_or(suspicious weights) × (1 − damp)`, where `noisy_or = 1 − ∏(1 − wᵢ)` and `damp = min(0.25, 0.5 × Σ reassuring weights)`.
- **Message:** rules-driven. `score = max(100 × S, hard_floor)`. Hard floors: OTP/PIN request 70; money request + urgency 72; digital-arrest script 55 (80 with urgency/secrecy/money/OTP); remote-access app 70; family emergency + money 72; fee-for-job 60; prize + money/link 65; investment guarantee 55; look-alike/IP/`@` link 60 (72 with KYC/threat/OTP/urgency). An optional LLM can add one `llm_assessment` signal (weight ≤ 0.3) but cannot lower anything.
- **Combined:** `score = min(100, 0.6 × max + 0.4 × mean + bonus)`. Bonus is +15 when image, voice and message are all ≥ 50, or +10 when two or more are ≥ 50 including a message of a known scam story (family emergency, UPI payment, digital arrest, bank/KYC). The bonus is never negative, and a `coordinated_impersonation` signal is added when it applies, so one weak modality cannot hide a strong one.
- **Confidence** is separate from risk. Image/audio: `|p − 0.5| > 0.35` high, `> 0.15` medium, else low; one step down for each of *degraded input* (small image, clip < 3 s, noisy recording) and *conflict* (model vs metadata, or windows disagreeing). Message: low for very short text, high with a hard signal or ≥ 3 suspicious signals. Combined: the confidence of the highest-scoring modality.

## Explanations are grounded

1. Detectors produce `Signal` objects (id, value, direction, weight, plain-language detail). A check that cannot run is omitted and noted under limitations.
2. The **template explainer** builds text from the highest-weight signals' own sentences, so it is deterministic and works with no API key.
3. The **LLM explainer** (optional) receives only the signal list (message/URL signal values are removed), is told not to state facts absent from it, and must return sentences with `signal_ids`. Sentences citing no real id are dropped; sentences with certainty wording ("definitely", "100%", "is fake") are dropped; if fewer than two survive, or on any error/timeout (12 s), the template is used.

## Design decisions
- **Offline first:** the message detector and URL checker need no network; the LLM is an upgrade.
- **Lazy + warm models:** loaded on first use, cached, and warmed in a background thread at startup.
- **No persistence:** in-memory processing; temp files (audio decode only) are deleted at once.
- **Weak signals stay weak:** ELA, frequency and prosody checks carry small weights and say so in their text.
- **Probabilities are never shown as 100%/0%:** wording is capped at "over 99%" / "under 1%".
- **CORS** allows the configured web origin and `chrome-extension://*`.

## API
`GET /api/health` · `GET /api/samples` · `GET /api/samples/{id}/file` · `POST /api/analyze/{image|audio|message|combined}` · `POST /api/analyze/sample/{id}`.
Errors are `{ "code": "...", "message": "..." }` (e.g. `invalid_image`, `file_too_large`, `audio_silent`, `text_too_long`, `no_input`).
