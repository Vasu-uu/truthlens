# TruthLens demo samples

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
