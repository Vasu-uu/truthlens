# 3-minute demo: "Son in trouble"

**Story:** A mother gets a voice note, a photo and a WhatsApp message from an "unknown number" claiming to be her son: he's had an accident and needs ₹25,000 on UPI *right now*, and she mustn't tell his father.

## Before you start (5 min, once)
1. Start the backend and frontend (README quickstart). Wait for the backend log line `model warm-up finished`, so the first click is fast.
2. `python scripts/make_samples.py` (creates the synthetic voice clips).
3. **Add an AI-generated photo** of a person to `backend/samples/image/ai/` (generate one yourself; none is bundled). Also add a real photo of the same kind to `image/real/`. Optional but powerful: a real voice note of a teammate in `audio/real/`.
4. Open the app on **Samples** and have the extension's side panel ready.
5. Practice with your own files once. Results on your files are what you'll show; don't promise numbers you haven't seen.

## Script

**0:00 - Hook (20 s).** "In India, scams that use a cloned voice, a fake photo and an urgent UPI request are rising. Most people can't tell. TruthLens shows *why* something looks fake, and it's honest about what it can't know."

**0:20 - The message (35 s).** Analyze tab → **Message** → paste the sample "son in trouble" text, set *WhatsApp*. Point at: the gauge (**High**), the highlighted phrases labelled *Family emergency, Urgency, Secrecy*, the extracted UPI ID and amount, the scam-type badge. Open one signal: "every card is something we measured, and tapping it tells you why it matters."

**0:55 - The voice (40 s).** **Voice** tab → upload the TTS clip (or record live on the mic). Show spectrogram + waveform, the verdict and its **confidence badge**. Say: "Compression from WhatsApp reduces accuracy: that's in the limitations section, which is always visible." If you have a real voice note, run it too and show the contrast.

**1:35 - The photo (30 s).** **Image** tab → AI photo. Drag the compare slider over the attention heat map; toggle ELA. Say: "The heat map shows where the model looked, not proof of editing." Then a real photo for contrast.

**2:05 - Put it together (35 s).** **Combined** tab: add all three (or press *Run combined demo* on Samples). Show the per-check cards and the **"coordinated impersonation"** banner, and how the score is boosted *only* because the pieces fit one scam story.

**2:40 - What to do (20 s).** Scroll to *What to do next*: call him on his saved number, don't pay to "verify", report at 1930 / cybercrime.gov.in. Click **Download report**. Show the extension: right-click a suspicious image on any page → side panel.

**3:00 - Close.** "Explainable, privacy-first, and honest about its limits. Files are never stored."

## If something goes wrong
- *Backend offline banner:* start the backend; reload.
- *First request slow:* models still warming; wait for the log line, or use Samples.
- *A verdict surprises you:* that's a feature. Open the signals, explain the confidence, point to limitations. Never claim the model is always right.
