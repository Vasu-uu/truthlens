import { useEffect, useRef, useState } from "react";
import { useToast } from "./Toasts";
import type { AnalysisResult, Media, Modality } from "../types";
import AudioPanel from "./AudioPanel";
import Gauge, { LEVEL_UI } from "./Gauge";
import ImagePanel from "./ImagePanel";
import MessagePanel from "./MessagePanel";
import SignalCard from "./SignalCard";

const CONF_TEXT = { low: "Low confidence", medium: "Medium confidence", high: "High confidence" } as const;
const MOD_LABEL: Record<Modality, string> = { image: "Image", audio: "Voice", message: "Message", combined: "Combined" };

function Section({ title, children, id }: { title: string; children: React.ReactNode; id?: string }) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-line bg-panel/70 p-4 sm:p-5">
      <h2 id={id} className="mb-3 text-base font-bold text-slate-100">{title}</h2>
      {children}
    </section>
  );
}

async function downloadPng(): Promise<void> {
  const el = document.getElementById("report-root");
  if (!el) return;
  const { default: html2canvas } = await import("html2canvas-pro");
  const canvas = await html2canvas(el, { backgroundColor: "#0b1020", scale: 2, useCORS: true });
  const a = document.createElement("a");
  a.href = canvas.toDataURL("image/png");
  a.download = `truthlens-report-${new Date().toISOString().slice(0, 10)}.png`;
  a.click();
}

export default function ResultView({ result, media, fromHistory = false }: { result: AnalysisResult; media: Media; fromHistory?: boolean }) {
  const toast = useToast();
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [exporting, setExporting] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);

  const exportPng = async () => {
    setExporting(true);
    try {
      await downloadPng();
    } catch {
      toast("Could not create the image. Try “Print / save PDF” instead.");
    } finally {
      setExporting(false);
    }
  };
  const a = result.artifacts;
  const parts = a.parts;
  const isCombined = result.modality === "combined";
  const sus = result.signals.filter((s) => s.direction === "suspicious").length;

  const panels = (m: Modality, art: typeof a) => {
    if (m === "image") return <ImagePanel a={art} original={media.imageUrl} />;
    if (m === "audio") return <AudioPanel a={art} audioUrl={media.audioUrl} />;
    if (m === "message") return <MessagePanel a={art} text={media.text} />;
    return null;
  };

  return (
    <div className="rise space-y-4" id="report-root">
      <div className="no-print flex flex-wrap items-center justify-between gap-2" data-html2canvas-ignore="true">
        {fromHistory ? (
          <p className="text-xs text-amber-200">Saved summary. Your files and message text are not kept, so previews and highlights are not shown.</p>
        ) : <span />}
        <div className="flex gap-2">
          <button onClick={exportPng} disabled={exporting} className="rounded-lg border border-line bg-panel2 px-3 py-2 text-xs font-semibold hover:border-slate-500 disabled:opacity-50">
            {exporting ? "Preparing…" : "⬇ Download report (PNG)"}
          </button>
          <button onClick={() => window.print()} className="rounded-lg border border-line bg-panel2 px-3 py-2 text-xs font-semibold hover:border-slate-500">
            🖨 Print / save PDF
          </button>
        </div>
      </div>
      <div className="grid gap-5 rounded-3xl border border-line bg-panel/80 p-5 sm:grid-cols-[auto_1fr] sm:p-7">
        <Gauge score={result.risk_score} level={result.risk_level} />
        <div className="min-w-0 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{MOD_LABEL[result.modality]} check</p>
          <h1 ref={heading} tabIndex={-1} className={`text-2xl font-extrabold leading-tight sm:text-3xl ${LEVEL_UI[result.risk_level].text}`}>{result.headline}</h1>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-line bg-panel2 px-3 py-1" title="How sure TruthLens is about this verdict (not the risk itself)">
              ◎ {CONF_TEXT[result.confidence]}
            </span>
            <span className="rounded-full border border-line bg-panel2 px-3 py-1">{sus} warning sign{sus === 1 ? "" : "s"} found</span>
            <span className="rounded-full border border-line bg-panel2 px-3 py-1">{(result.processing_ms / 1000).toFixed(1)}s</span>
          </div>
          <p className="text-sm leading-relaxed text-slate-200">{result.explanation}</p>
          <p className="text-xs text-slate-400">
            TruthLens estimates likelihood from measurable signals. It is not proof either way.
            {a.explanation_source === "llm" ? " Wording written by an AI assistant from the signals below." : ""}
          </p>
        </div>
      </div>

      {isCombined && a.per_modality && (
        <Section title="What each check found" id="h-per">
          <ul className="grid gap-3 sm:grid-cols-3">
            {a.per_modality.map((p) => (
              <li key={p.modality} className="rounded-xl border border-line bg-panel2 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{MOD_LABEL[p.modality]}</p>
                <p className={`mt-1 text-2xl font-extrabold ${LEVEL_UI[p.risk_level].text}`}>
                  <span aria-hidden="true">{LEVEL_UI[p.risk_level].icon} </span>{p.risk_score}
                </p>
                <p className="text-xs text-slate-300">{LEVEL_UI[p.risk_level].label} · {CONF_TEXT[p.confidence].toLowerCase()}</p>
              </li>
            ))}
          </ul>
          {a.cross_modal_reason && (
            <p className="mt-3 rounded-xl border border-red-400/40 bg-red-400/10 p-3 text-sm text-red-100">
              ⚠ Pattern match: {a.cross_modal_reason}. Score boosted by {a.cross_modal_bonus} points.
            </p>
          )}
        </Section>
      )}

      {isCombined && parts
        ? (["message", "audio", "image"] as const).map((m) => {
            const part = parts[m];
            return part && <Section key={m} title={`${MOD_LABEL[m]} details`} id={`h-${m}`}>{panels(m, part.artifacts)}</Section>;
          })
        : !isCombined && (
            <Section title={`${MOD_LABEL[result.modality]} details`} id="h-detail">{panels(result.modality, a)}</Section>
          )}

      <Section title="Evidence (signals)" id="h-signals">
        <p className="mb-3 text-xs text-slate-400">Every item below was measured or matched, strongest first. Tap one for the plain-language reason.</p>
        <ul className="space-y-2">{result.signals.map((s) => <SignalCard key={s.id + s.category} s={s} />)}</ul>
      </Section>

      <Section title="What to do next" id="h-next">
        <ul className="space-y-2">
          {result.next_steps.map((s, i) => (
            <li key={i}>
              <label className="flex cursor-pointer items-start gap-3 rounded-lg p-2 text-sm hover:bg-panel2">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-cyan-400" checked={!!checked[i]} onChange={(e) => setChecked({ ...checked, [i]: e.target.checked })} />
                <span className={checked[i] ? "text-slate-500 line-through" : ""}>{s}</span>
              </label>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Limitations: please read" id="h-limits">
        <details open className="group">
          <summary className="cursor-pointer text-sm font-medium text-amber-200">{result.limitations.length} things to keep in mind</summary>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-300">
            {result.limitations.map((l, i) => <li key={i}>{l}</li>)}
          </ul>
        </details>
        <p className="mt-3 text-xs text-slate-500">
          Models: {Object.entries(result.model_versions).map(([k, v]) => `${k}: ${v}`).join(" · ")}
        </p>
      </Section>
    </div>
  );
}
