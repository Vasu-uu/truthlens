import { DEFAULTS, ExtError, checkHealth, normalizeUrl } from "./api.js";

const backend = document.getElementById("backend");
const app = document.getElementById("app");
const status = document.getElementById("status");

function say(text, ok) {
  status.textContent = text;
  status.style.color = ok ? "#6ee7b7" : "#fca5a5";
}

async function load() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  backend.value = s.backendUrl;
  app.value = s.appUrl;
}

function read() {
  return { backendUrl: normalizeUrl(backend.value, DEFAULTS.backendUrl), appUrl: normalizeUrl(app.value, DEFAULTS.appUrl) };
}

document.getElementById("save").addEventListener("click", async () => {
  try {
    const v = read();
    await chrome.storage.sync.set(v);
    backend.value = v.backendUrl;
    app.value = v.appUrl;
    say("Saved.", true);
  } catch (e) {
    say(e instanceof ExtError ? e.message : "Could not save.", false);
  }
});

document.getElementById("test").addEventListener("click", async () => {
  try {
    say("Testing…", true);
    const h = await checkHealth(read().backendUrl);
    say(`Connected. Backend is ${h.status}, running on ${h.device}.`, true);
  } catch (e) {
    say(e instanceof ExtError ? e.message : "Connection failed.", false);
  }
});

load();
