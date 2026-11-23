import { useState } from "react";
import type { Artifacts } from "../types";

const src = (b64?: string): string | undefined => (b64 ? `data:image/png;base64,${b64}` : undefined);

/** Original vs overlay with a slider; toggle between attention map and ELA. */
export default function ImagePanel({ a, original }: { a: Artifacts; original?: string }) {
  const [mode, setMode] = useState<"heat" | "ela">(a.heatmap_png_base64 ? "heat" : "ela");
  const [pos, setPos] = useState(50);
  const base = original ?? src(a.original_png_base64);
  const overlay = mode === "heat" ? src(a.heatmap_png_base64) : src(a.ela_png_base64);
  if (!base) return null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-200">Where the detector looked</h3>
        <div role="group" aria-label="Overlay type" className="flex gap-1 rounded-lg border border-line p-1 text-xs">
          {a.heatmap_png_base64 && (
            <button aria-pressed={mode === "heat"} onClick={() => setMode("heat")} className={`rounded-md px-2.5 py-1 ${mode === "heat" ? "bg-accent font-bold text-slate-950" : "text-slate-300"}`}>
              Attention map
            </button>
          )}
          {a.ela_png_base64 && (
            <button aria-pressed={mode === "ela"} onClick={() => setMode("ela")} className={`rounded-md px-2.5 py-1 ${mode === "ela" ? "bg-accent font-bold text-slate-950" : "text-slate-300"}`}>
              Error level (ELA)
            </button>
          )}
        </div>
      </div>
      <div className="relative mx-auto w-full max-w-xl select-none overflow-hidden rounded-xl border border-line bg-black">
        <img src={base} alt="Original image" className="block w-full" draggable={false} />
        {overlay && (
          <img
            src={overlay}
            alt={mode === "heat" ? "Attention map overlay" : "Error level analysis overlay"}
            className="absolute inset-0 h-full w-full object-fill"
            style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
            draggable={false}
          />
        )}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white/90" style={{ left: `${pos}%` }} aria-hidden="true" />
        <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px]">{mode === "heat" ? "Heat map" : "ELA"}</span>
        <span className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px]">Original</span>
      </div>
      <label className="mx-auto flex max-w-xl items-center gap-3 text-xs text-slate-400">
        Compare
        <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(Number(e.target.value))} aria-label="Slide to compare the original with the overlay" className="flex-1 accent-cyan-400" />
      </label>
      <p className="mx-auto max-w-xl text-xs text-slate-400">
        {mode === "heat"
          ? `Warmer areas influenced the AI-generation estimate most (${a.heatmap_method ?? "model attention"}). It shows where the model looked, not proof of editing.`
          : "Brighter areas recompress differently. This is a weak, uncalibrated hint; ordinary JPEG edges also light up."}
      </p>
    </div>
  );
}
