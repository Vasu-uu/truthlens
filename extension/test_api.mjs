// Run: node extension/test_api.mjs   (needs the backend running on http://localhost:8000)
import assert from "node:assert/strict";
import { ExtError, analyzeImageUrl, analyzeText, checkHealth, normalizeUrl } from "./api.js";

const BASE = process.env.TRUTHLENS_URL || "http://localhost:8000";
let pass = 0;
const t = async (name, fn) => {
  try {
    await fn();
    pass++;
    console.log("PASS", name);
  } catch (e) {
    console.log("FAIL", name, "-", e.message);
    process.exitCode = 1;
  }
};
const rejects = async (p, code) => {
  try {
    await p;
  } catch (e) {
    assert.ok(e instanceof ExtError, `expected ExtError, got ${e}`);
    assert.equal(e.code, code);
    return e;
  }
  assert.fail("expected rejection");
};

await t("health", async () => assert.equal((await checkHealth(BASE)).status, "ok"));
await t("scam text -> high", async () => {
  const r = await analyzeText(BASE, "Dear customer your SBI account will be blocked. Share the OTP immediately.");
  assert.equal(r.risk_level, "high");
  assert.ok(r.signals.length && r.next_steps.length);
});
await t("friendly text still low", async () => {
  const r = await analyzeText(BASE, "Hey are we still meeting for lunch tomorrow at one? Let me know.");
  assert.equal(r.risk_level, "low");
});
await t("image url -> analysed", async () => {
  const r = await analyzeImageUrl(BASE, `${BASE}/api/samples/image-real-coffee/file`);
  assert.equal(r.modality, "image");
});
await t("empty text rejected", () => rejects(analyzeText(BASE, "   "), "empty_text"));
await t("too long text rejected", () => rejects(analyzeText(BASE, "x".repeat(5001)), "text_too_long"));
await t("blob url explained", () => rejects(analyzeImageUrl(BASE, "blob:https://x.com/abc"), "unsupported_image"));
await t("missing image explained", () => rejects(analyzeImageUrl(BASE, `${BASE}/api/samples/nope/file`), "image_fetch_failed"));
await t("non-image explained", () => rejects(analyzeImageUrl(BASE, `${BASE}/api/health`), "unsupported_image"));
await t("backend offline is friendly", async () => {
  const e = await rejects(analyzeText("http://localhost:9", "hello there friend"), "backend_offline");
  assert.match(e.message, /Can't reach the TruthLens backend/);
});
await t("normalizeUrl", () => {
  assert.equal(normalizeUrl(" http://localhost:8000/ ", "x"), "http://localhost:8000");
  assert.throws(() => normalizeUrl("ftp://x", "y"), ExtError);
  assert.equal(normalizeUrl("", "http://a.b"), "http://a.b");
});
console.log(`\n${pass} passed`);
