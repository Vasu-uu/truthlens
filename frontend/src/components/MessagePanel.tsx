import type { Artifacts } from "../types";

const TACTIC: Record<string, { label: string; cls: string }> = {
  urgency: { label: "Urgency", cls: "bg-amber-400/25 decoration-amber-300" },
  threat: { label: "Threat", cls: "bg-orange-500/25 decoration-orange-300" },
  money: { label: "Money request", cls: "bg-red-500/25 decoration-red-300" },
  credentials: { label: "OTP / PIN request", cls: "bg-fuchsia-500/25 decoration-fuchsia-300" },
  authority: { label: "Authority claim", cls: "bg-sky-500/25 decoration-sky-300" },
  family: { label: "Family emergency", cls: "bg-pink-500/25 decoration-pink-300" },
  prize: { label: "Prize bait", cls: "bg-violet-500/25 decoration-violet-300" },
  job: { label: "Job lure", cls: "bg-lime-500/25 decoration-lime-300" },
  investment: { label: "Investment pitch", cls: "bg-teal-500/25 decoration-teal-300" },
  secrecy: { label: "Secrecy", cls: "bg-rose-500/25 decoration-rose-300" },
  remote_access: { label: "Remote access", cls: "bg-red-600/30 decoration-red-300" },
  romance: { label: "Romance lure", cls: "bg-purple-500/25 decoration-purple-300" },
  link: { label: "Link", cls: "bg-cyan-500/25 decoration-cyan-300" },
  grammar: { label: "Odd wording", cls: "bg-slate-500/25 decoration-slate-300" },
};
const info = (t: string) => TACTIC[t] ?? { label: t, cls: "bg-slate-500/25 decoration-slate-300" };

export default function MessagePanel({ a, text }: { a: Artifacts; text?: string }) {
  const hl = a.highlights ?? [];
  const parts: { t: string; tactic?: string }[] = [];
  if (text) {
    let at = 0;
    for (const h of hl) {
      if (h.start > at) parts.push({ t: text.slice(at, h.start) });
      parts.push({ t: text.slice(h.start, h.end), tactic: h.tactic });
      at = h.end;
    }
    if (at < text.length) parts.push({ t: text.slice(at) });
  }
  const used = [...new Set(hl.map((h) => h.tactic))];
  const e = a.entities;
  const hasEntities = e && (e.upi_ids.length || e.urls.length || e.phone_numbers.length || e.amounts.length);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-200">Message type</h3>
        <span className="rounded-full border border-cyan-400/40 bg-cyan-400/10 px-3 py-1 text-xs font-bold text-cyan-100">
          {a.scam_type_label ?? a.scam_type ?? "n/a"}
        </span>
      </div>
      {text && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Suspicious phrases highlighted</h3>
          <p className="whitespace-pre-wrap rounded-xl border border-line bg-panel2 p-4 text-sm leading-7">
            {parts.map((p, i) =>
              p.tactic ? (
                <mark key={i} title={info(p.tactic).label} className={`rounded px-1 text-inherit underline decoration-2 underline-offset-4 ${info(p.tactic).cls}`}>
                  {p.t}
                  <sup className="ml-0.5 text-[9px] font-bold uppercase text-slate-300">{info(p.tactic).label}</sup>
                </mark>
              ) : (
                <span key={i}>{p.t}</span>
              ),
            )}
          </p>
          {used.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-2 text-xs" aria-label="Legend">
              {used.map((t) => (
                <li key={t} className={`rounded-full px-2.5 py-1 ${info(t).cls} underline decoration-2 underline-offset-4`}>{info(t).label}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {hasEntities && e && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Details found in the message</h3>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            {([["UPI IDs", e.upi_ids], ["Links (not opened)", e.urls], ["Phone numbers", e.phone_numbers], ["Amounts", e.amounts]] as const).map(
              ([k, v]) => v.length > 0 && (
                <div key={k} className="rounded-xl border border-line bg-panel/70 p-3">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{k}</dt>
                  <dd className="mt-1 break-all font-mono text-xs text-slate-200">{v.join(", ")}</dd>
                </div>
              ),
            )}
          </dl>
        </div>
      )}
    </div>
  );
}
