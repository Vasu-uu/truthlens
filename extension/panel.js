// Renders the stored state. All dynamic text goes through textContent (never innerHTML).

const root = document.getElementById("root");
const ICON = { low: "✓", medium: "!", high: "⚠" };
const LABEL = { low: "Low risk", medium: "Medium risk", high: "High risk" };
const CONF = { low: "Low confidence", medium: "Medium confidence", high: "High confidence" };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k) n.append(k);
  return n;
}

function card(title, ...kids) {
  return el("section", { class: "card" }, title ? el("h2", { text: title }) : null, ...kids);
}

function render(state) {
  root.replaceChildren();
  if (!state || state.status === "idle") {
    root.append(
      card(
        "How to use",
        el("p", { text: "Right-click an image and choose “Check image with TruthLens”, or select some text and choose “Check selected text with TruthLens”." }),
        el("p", { class: "muted", text: "Needs the TruthLens backend running on your computer. You can change its address in the extension options." }),
      ),
    );
    return;
  }
  if (state.status === "loading") {
    root.append(card(null, el("p", { text: state.kind === "image" ? "Checking the image…" : "Checking the text…" }), el("div", { class: "pulse" }), el("div", { class: "pulse" })));
    return;
  }
  if (state.status === "error") {
    root.append(card("Couldn’t check this", el("p", { text: state.message })));
    root.lastChild.classList.add("err");
    root.append(el("a", { class: "btn", href: "#", id: "opts", text: "Open extension options" }));
    document.getElementById("opts").addEventListener("click", (e) => {
      e.preventDefault();
      chrome.runtime.openOptionsPage();
    });
    return;
  }

  const r = state.result;
  const lvl = r.risk_level;
  root.append(
    card(
      state.kind === "image" ? "Image check" : "Message check",
      el("span", { class: `badge ${lvl}` }, el("span", { "aria-hidden": "true", text: ICON[lvl] }), el("span", { text: LABEL[lvl] })),
      el("div", { class: "score", text: `${r.risk_score}/100` }),
      el("p", { text: r.headline }),
      el("p", { class: "muted", text: `${CONF[r.confidence]} · likelihood, not proof` }),
    ),
  );

  const top = [...r.signals].filter((s) => s.direction !== "neutral").sort((a, b) => b.weight - a.weight).slice(0, 3);
  if (top.length) {
    const list = el("ul", { class: "sig" });
    for (const s of top) {
      list.append(
        el("li", {}, el("span", { class: `tag ${s.direction}`, text: s.direction === "suspicious" ? "▲ SUSPICIOUS" : "✓ REASSURING" }), el("b", { text: s.name }), el("span", { class: "muted", text: s.detail })),
      );
    }
    root.append(card("Top evidence", list));
  }

  if (r.next_steps?.length) {
    const list = el("ul");
    for (const s of r.next_steps.slice(0, 3)) list.append(el("li", { text: s }));
    root.append(card("What to do next", list));
  }

  if (r.limitations?.length) root.append(el("p", { class: "muted", text: `Limitation: ${r.limitations[0]}` }));
  root.append(el("a", { class: "btn", href: state.appUrl || "http://localhost:5173", target: "_blank", rel: "noopener", text: "Open full report in TruthLens" }));
}

async function init() {
  const { state } = await chrome.storage.session.get("state");
  render(state);
}
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.state) render(changes.state.newValue);
});
init();
