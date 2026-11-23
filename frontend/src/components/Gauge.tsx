import type { Level } from "../types";

export const LEVEL_UI: Record<Level, { label: string; icon: string; text: string; stroke: string; chip: string }> = {
  low: { label: "Low risk", icon: "✓", text: "text-emerald-300", stroke: "#34d399", chip: "border-emerald-400/50 bg-emerald-400/10 text-emerald-200" },
  medium: { label: "Medium risk", icon: "!", text: "text-amber-300", stroke: "#fbbf24", chip: "border-amber-400/50 bg-amber-400/10 text-amber-200" },
  high: { label: "High risk", icon: "⚠", text: "text-red-300", stroke: "#f87171", chip: "border-red-400/50 bg-red-400/10 text-red-200" },
};

/** Semicircle gauge. Level is conveyed by text and icon as well as colour. */
export default function Gauge({ score, level }: { score: number; level: Level }) {
  const ui = LEVEL_UI[level];
  const arc = Math.PI * 80;
  return (
    <figure className="m-0 text-center" aria-label={`Risk score ${score} out of 100: ${ui.label}`}>
      <svg viewBox="0 0 200 118" className="mx-auto w-56" role="img" aria-hidden="true">
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#263252" strokeWidth="14" strokeLinecap="round" />
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={ui.stroke}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={arc}
          strokeDashoffset={arc * (1 - score / 100)}
          style={{ transition: "stroke-dashoffset .9s cubic-bezier(.2,.8,.2,1)" }}
        />
        <text x="100" y="88" textAnchor="middle" fontSize="42" fontWeight="800" fill="#f1f5ff">{score}</text>
        <text x="100" y="108" textAnchor="middle" fontSize="11" fill="#94a3c8">out of 100</text>
      </svg>
      <figcaption className={`mt-1 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-bold ${ui.chip}`}>
        <span aria-hidden="true">{ui.icon}</span> {ui.label}
      </figcaption>
    </figure>
  );
}
