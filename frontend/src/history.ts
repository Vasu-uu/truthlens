import type { AnalysisResult } from "./types";

const KEY = "truthlens.history.v1";
const MAX = 10;

export interface HistoryEntry {
  id: string;
  ts: number;
  result: AnalysisResult;
}

/**
 * Keep only the verdict summary. Drops images, audio peaks, per-part artifacts, and anything
 * that could echo the user's content: extracted entities (UPI IDs, links, numbers) and the
 * matched phrases that message/URL signals carry as their `value`.
 */
function strip(r: AnalysisResult): AnalysisResult {
  const art: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(r.artifacts)) {
    if (k.endsWith("_base64") || ["waveform_peaks", "parts", "highlights", "entities"].includes(k)) continue;
    art[k] = v;
  }
  const signals = r.signals.map((s) =>
    s.category === "message" || s.category === "url" || s.category === "cross-modal" ? { ...s, value: typeof s.value === "number" ? s.value : null } : s,
  );
  return { ...r, artifacts: art, signals };
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
    return Array.isArray(list) ? list.slice(0, MAX) : [];
  } catch {
    return [];
  }
}

export function addHistory(r: AnalysisResult): HistoryEntry[] {
  const entry: HistoryEntry = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, ts: Date.now(), result: strip(r) };
  const next = [entry, ...loadHistory()].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage full or blocked: history is a convenience only */
  }
  return next;
}

export function clearHistory(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
