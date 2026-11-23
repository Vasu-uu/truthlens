# Privacy

TruthLens is designed to analyse sensitive material (family voice notes, private photos, scam messages), so it keeps as little as possible.

## What the backend does with your input
- **Images and audio** are read into memory, analysed and discarded. Audio decoding briefly uses a temporary file, which is deleted immediately after decoding (in a `finally` block).
- **Message text** is analysed in memory and discarded.
- **Logs** never contain file contents, message text, or extracted entities. Errors are logged by type only.
- **No database, no accounts, no analytics.**

## What leaves your machine
- **Model downloads:** on first use, model weights are fetched from Hugging Face. No user data is sent.
- **LLM provider (optional, off by default: `LLM_PROVIDER=none`).** If you configure one:
  - the *explanation* step receives only the structured signal list (names, weights, plain-language details). Values taken from message text and links are removed before sending;
  - the *message classification* step receives the **message text itself**. Set `LLM_SEND_TEXT=false` to disable this;
  - the provider's own retention policy then applies. With `LLM_PROVIDER=ollama` everything stays on your computer.
- **Links in messages are never opened.** They are analysed as text only.

## What the browser stores
- **History** (last 10 checks) lives in your browser's `localStorage`: only the verdict summary (score, level, headline, signal names and explanations). It does **not** include uploaded files, recordings, message text, extracted links/UPI IDs/numbers, or matched phrases. "Clear history" removes it.
- The **Chrome extension** keeps its settings in `chrome.storage.sync` and the latest result in `chrome.storage.session`, which is cleared when the browser closes. Selected text and images are sent only to the backend address you configure.

## Your responsibilities
- Only analyse content you have the right to analyse; get consent before checking someone else's voice.
- If you deploy TruthLens on a shared server, add HTTPS and access control; the app ships without authentication.
