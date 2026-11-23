// Pure API helpers (no chrome.* calls) so they can be unit-tested from Node.

export const DEFAULTS = { backendUrl: "http://localhost:8000", appUrl: "http://localhost:5173" };
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_TEXT_CHARS = 5000;

/** Error carrying a short code and a message that is safe to show to people. */
export class ExtError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export function normalizeUrl(value, fallback) {
  const raw = (value || "").trim() || fallback;
  try {
    const u = new URL(raw);
    if (u.protocol !== "http:" && u.protocol !== "https:") throw new Error("protocol");
    return u.origin + u.pathname.replace(/\/+$/, "");
  } catch {
    throw new ExtError("bad_url", `"${raw}" is not a valid http(s) address.`);
  }
}

async function callBackend(baseUrl, path, init) {
  let res;
  try {
    res = await fetch(baseUrl + path, init);
  } catch {
    throw new ExtError(
      "backend_offline",
      `Can't reach the TruthLens backend at ${baseUrl}. Start it (see the README), or fix the address in the extension options.`,
    );
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    throw new ExtError(body?.code || `http_${res.status}`, body?.message || `The backend returned an error (${res.status}).`);
  }
  return body;
}

export async function checkHealth(baseUrl) {
  return callBackend(baseUrl, "/api/health");
}

/** Download an image in the extension, then send its bytes to the backend. */
export async function analyzeImageUrl(baseUrl, srcUrl) {
  if (!srcUrl || srcUrl.startsWith("blob:")) {
    throw new ExtError("unsupported_image", "This image can't be read from outside the page (it is a private blob). Save it and upload it in the TruthLens web app instead.");
  }
  let blob;
  try {
    const r = await fetch(srcUrl, { credentials: "omit" });
    if (!r.ok) throw new Error(String(r.status));
    blob = await r.blob();
  } catch {
    throw new ExtError("image_fetch_failed", "Couldn't download this image. It may be private, expired or blocked by the site. Try saving it and uploading it in the web app.");
  }
  if (blob.size > MAX_IMAGE_BYTES) throw new ExtError("file_too_large", "This image is larger than 10 MB.");
  if (blob.type && !blob.type.startsWith("image/")) throw new ExtError("unsupported_image", "That link isn't an image file TruthLens can read.");
  const fd = new FormData();
  fd.append("file", blob, "image");
  return callBackend(baseUrl, "/api/analyze/image", { method: "POST", body: fd });
}

export async function analyzeText(baseUrl, text) {
  const t = (text || "").trim();
  if (!t) throw new ExtError("empty_text", "No text was selected.");
  if (t.length > MAX_TEXT_CHARS) throw new ExtError("text_too_long", `The selection is longer than ${MAX_TEXT_CHARS} characters. Select a shorter part.`);
  return callBackend(baseUrl, "/api/analyze/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: t }),
  });
}
