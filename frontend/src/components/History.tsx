import { LEVEL_UI } from "./Gauge";
import type { HistoryEntry } from "../history";

const LABEL = { image: "Image", audio: "Voice", message: "Message", combined: "Combined" } as const;

interface Props {
  items: HistoryEntry[];
  onOpen: (e: HistoryEntry) => void;
  onClear: () => void;
}

export default function History({ items, onOpen, onClear }: Props) {
  return (
    <section aria-labelledby="h-history" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="h-history" className="text-xl font-bold">Recent checks</h2>
          <p className="text-sm text-slate-400">Saved only in this browser (last 10). Only the verdict summary is kept: never your files, recordings or message text.</p>
        </div>
        {items.length > 0 && (
          <button onClick={onClear} className="rounded-lg border border-red-400/50 px-4 py-2 text-sm font-semibold text-red-200 hover:bg-red-400/10">
            Clear history
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="rounded-2xl border border-line bg-panel/60 p-6 text-sm text-slate-300">Nothing here yet. Your checks will appear after you run one.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((e) => {
            const ui = LEVEL_UI[e.result.risk_level];
            return (
              <li key={e.id}>
                <button onClick={() => onOpen(e)} className="flex w-full items-center gap-4 rounded-xl border border-line bg-panel/70 p-3 text-left hover:border-slate-500">
                  <span className={`flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-lg border text-sm font-extrabold ${ui.chip}`}>
                    <span aria-hidden="true" className="text-xs leading-none">{ui.icon}</span>{e.result.risk_score}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{e.result.headline}</span>
                    <span className="block text-xs text-slate-400">
                      {LABEL[e.result.modality]} · {ui.label} · {new Date(e.ts).toLocaleString()}
                    </span>
                  </span>
                  <span aria-hidden="true" className="text-slate-500">›</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
