import { useState } from "react";
import type { Signal } from "../types";

const DIR = {
  suspicious: { tag: "▲ Suspicious", cls: "border-red-400/40 bg-red-400/10 text-red-200", bar: "bg-red-400" },
  reassuring: { tag: "✓ Reassuring", cls: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200", bar: "bg-emerald-400" },
  neutral: { tag: "● Neutral", cls: "border-slate-500/40 bg-slate-400/10 text-slate-300", bar: "bg-slate-400" },
} as const;

export default function SignalCard({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  const d = DIR[s.direction];
  return (
    <li className="rounded-xl border border-line bg-panel/70">
      <button
        className="flex w-full items-center gap-3 p-3 text-left"
        aria-expanded={open}
        aria-controls={`sig-${s.id}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${d.cls}`}>{d.tag}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold">{s.name}</span>
          {s.value !== null && s.value !== undefined && typeof s.value !== "boolean" && (
            <span className="block truncate text-xs text-slate-400">Measured: {String(s.value)}</span>
          )}
        </span>
        <span className="hidden w-24 shrink-0 sm:block" title={`Weight ${s.weight}`}>
          <span className="block h-1.5 overflow-hidden rounded-full bg-slate-700">
            <span className={`block h-full ${d.bar}`} style={{ width: `${Math.round(s.weight * 100)}%` }} />
          </span>
          <span className="mt-0.5 block text-right text-[10px] text-slate-400">weight {Math.round(s.weight * 100)}%</span>
        </span>
        <span aria-hidden="true" className={`text-slate-400 transition ${open ? "rotate-180" : ""}`}>⌄</span>
      </button>
      {open && (
        <div id={`sig-${s.id}`} className="border-t border-line px-3 pb-3 pt-2 text-sm text-slate-300">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Why this matters</p>
          {s.detail}
        </div>
      )}
    </li>
  );
}
