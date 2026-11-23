// TruthLens service worker: context menus -> backend -> side panel.
import { DEFAULTS, ExtError, analyzeImageUrl, analyzeText, normalizeUrl } from "./api.js";

const MENU_IMAGE = "truthlens-image";
const MENU_TEXT = "truthlens-text";

async function getConfig() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  return {
    backendUrl: normalizeUrl(s.backendUrl, DEFAULTS.backendUrl),
    appUrl: normalizeUrl(s.appUrl, DEFAULTS.appUrl),
  };
}

const setState = (state) => chrome.storage.session.set({ state });

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: MENU_IMAGE, title: "Check image with TruthLens", contexts: ["image"] });
    chrome.contextMenus.create({ id: MENU_TEXT, title: "Check selected text with TruthLens", contexts: ["selection"] });
  });
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});

/** Must run synchronously inside the click handler so Chrome treats it as a user gesture. */
function openPanel(tab) {
  const fallback = () =>
    chrome.windows.create({ url: chrome.runtime.getURL("panel.html"), type: "popup", width: 420, height: 680 });
  try {
    chrome.sidePanel.open({ tabId: tab.id }).catch(fallback);
  } catch {
    fallback();
  }
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_IMAGE && info.menuItemId !== MENU_TEXT) return;
  openPanel(tab ?? { id: undefined });
  run(info);
});

async function run(info) {
  const kind = info.menuItemId === MENU_IMAGE ? "image" : "message";
  await setState({ status: "loading", kind });
  try {
    const cfg = await getConfig();
    const result = kind === "image" ? await analyzeImageUrl(cfg.backendUrl, info.srcUrl) : await analyzeText(cfg.backendUrl, info.selectionText);
    await setState({ status: "result", kind, result, appUrl: cfg.appUrl, at: Date.now() });
  } catch (e) {
    const message = e instanceof ExtError ? e.message : "Something went wrong while checking this. Please try again.";
    await setState({ status: "error", kind, message, code: e instanceof ExtError ? e.code : "unknown" });
  }
}
