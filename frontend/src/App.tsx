import { useEffect, useRef, useState } from "react";
import { API, health } from "./api";
import Analyzer from "./components/Analyzer";
import ErrorBoundary from "./components/ErrorBoundary";
import History from "./components/History";
import HowItWorks from "./components/HowItWorks";
import ResultView from "./components/ResultView";
import Samples from "./components/Samples";
import { addHistory, clearHistory, loadHistory, type HistoryEntry } from "./history";
import type { AnalysisResult, Media } from "./types";

type View = "analyze" | "samples" | "history" | "how";
const NAV: [View, string][] = [["analyze", "Analyse"], ["samples", "Samples"], ["history", "History"], ["how", "How it works"]];

export default function App() {
  const [view, setView] = useState<View>("analyze");
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState<{ r: AnalysisResult; m: Media; saved: boolean } | null>(null);
  const [hist, setHist] = useState<HistoryEntry[]>(() => loadHistory());
  const [offline, setOffline] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    health().then(() => setOffline(false)).catch(() => setOffline(true));
  }, []);

  useEffect(() => {
    if (current) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [current]);

  const onResult = (r: AnalysisResult, m: Media) => {
    setCurrent({ r, m, saved: false });
    setHist(addHistory(r));
    setOffline(false);
  };
  const openSaved = (e: HistoryEntry) => {
    setCurrent({ r: e.result, m: {}, saved: true });
    setView("analyze");
  };

  return (
    <div className="mx-auto min-h-screen max-w-5xl px-4 pb-16 pt-6 sm:px-6">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-slate-950">Skip to content</a>
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 32 32" className="h-9 w-9" aria-hidden="true">
            <circle cx="16" cy="16" r="11" fill="none" stroke="#22d3ee" strokeWidth="3" />
            <circle cx="16" cy="16" r="4" fill="#22d3ee" />
          </svg>
          <div>
            <p className="text-xl font-extrabold tracking-tight">TruthLens</p>
            <p className="text-xs text-slate-400">Deepfake &amp; AI-fraud shield</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex flex-wrap gap-1 rounded-xl border border-line bg-panel/70 p-1 text-sm">
          {NAV.map(([id, label]) => (
            <button key={id} aria-current={view === id ? "page" : undefined} onClick={() => setView(id)}
              className={`rounded-lg px-3 py-2 font-semibold sm:px-4 ${view === id ? "bg-accent text-slate-950" : "text-slate-300 hover:bg-panel2"}`}>
              {label}
            </button>
          ))}
        </nav>
      </header>

      {offline && (
        <div role="alert" className="mb-6 rounded-xl border border-amber-400/50 bg-amber-400/10 p-4 text-sm text-amber-100">
          <strong>Can’t reach the TruthLens backend</strong> at <code>{API}</code>. Start it (see the README), then reload this page.
        </div>
      )}

      <main id="main" className="space-y-8">
        <ErrorBoundary>
          {view === "analyze" && (
            <>
              {!current && (
                <div className="max-w-2xl">
                  <h1 className="text-3xl font-extrabold leading-tight sm:text-4xl">Is that photo, voice note or message <span className="text-accent">real</span>?</h1>
                  <p className="mt-3 text-slate-300">Check suspicious content before you trust it or pay. TruthLens shows its evidence, says how sure it is, and tells you what to do next.</p>
                </div>
              )}
              <Analyzer onResult={onResult} busy={busy} setBusy={setBusy} />
              <div ref={resultRef} className="scroll-mt-4">
                {current && !busy && (
                  <ResultView key={`${current.r.processing_ms}-${current.r.risk_score}-${current.r.modality}-${current.saved}`}
                    result={current.r} media={current.m} fromHistory={current.saved} />
                )}
              </div>
            </>
          )}
          {view === "samples" && <Samples onResult={(r, m) => { onResult(r, m); setView("analyze"); }} busy={busy} setBusy={setBusy} />}
          {view === "history" && <History items={hist} onOpen={openSaved} onClear={() => { clearHistory(); setHist([]); }} />}
          {view === "how" && <HowItWorks />}
        </ErrorBoundary>
      </main>

      <footer className="mt-14 border-t border-line pt-6 text-xs leading-relaxed text-slate-500">
        <p>TruthLens is an aid, not a legal or forensic tool. Detectors are imperfect and can be wrong in both directions. If money is at risk, call your bank on the number printed on your card, and report fraud at 1930 or cybercrime.gov.in.</p>
      </footer>
    </div>
  );
}
