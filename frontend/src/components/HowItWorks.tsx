const CHECKS = [
  {
    title: "Image",
    icon: "🖼️",
    does: [
      "A pretrained AI-image classifier estimates how likely the picture is AI-generated.",
      "Metadata is read for camera details, editing or AI-tool names and embedded generator settings.",
      "Error Level Analysis and a frequency check look for patchy recompression or repeating AI up-sampling patterns (weak hints).",
      "A heat map shows which regions the classifier relied on.",
    ],
    cannot: "It cannot tell a heavily edited real photo from an AI image with certainty, and newer generators can slip past it.",
  },
  {
    title: "Voice",
    icon: "🎙️",
    does: [
      "A pretrained anti-spoofing model estimates how likely the voice is synthetic or cloned.",
      "Pitch variation, pause rhythm, background noise and frequency range are measured as supporting hints.",
      "A spectrogram lets you see the sound yourself.",
    ],
    cannot: "WhatsApp and phone-call compression hide the traces detectors rely on, and very short clips are unreliable.",
  },
  {
    title: "Message",
    icon: "💬",
    does: [
      "Named rules look for pressure, money and OTP requests, impersonation of banks and officials, family-emergency scripts, prize, job and investment bait.",
      "Links are checked by their text only (look-alike domains, shorteners, odd endings). They are never opened.",
      "An optional AI assistant can re-read the wording. It can add evidence but can never lower a hard warning.",
    ],
    cannot: "A new, well-written scam may not match any rule, and a genuine alert can occasionally look alarming.",
  },
];

function Box({ x, y, w, h, title, sub, tone = "#18223d" }: { x: number; y: number; w: number; h: number; title: string; sub?: string; tone?: string }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={12} fill={tone} stroke="#263252" />
      <text x={x + w / 2} y={y + (sub ? h / 2 - 4 : h / 2 + 5)} textAnchor="middle" fill="#e6ecff" fontSize="14" fontWeight="700">{title}</text>
      {sub && <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle" fill="#94a3c8" fontSize="11">{sub}</text>}
    </g>
  );
}

export default function HowItWorks() {
  const arrow = (x1: number, y1: number, x2: number, y2: number) => (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#22d3ee" strokeWidth="2" markerEnd="url(#arr)" />
  );
  return (
    <section aria-labelledby="h-how" className="space-y-8">
      <div className="max-w-2xl">
        <h2 id="h-how" className="text-2xl font-bold">How TruthLens works</h2>
        <p className="mt-2 text-slate-300">Every verdict is built from small, named pieces of evidence. You can see each one, and the explanation is written only from them.</p>
      </div>

      <figure className="m-0 overflow-x-auto rounded-2xl border border-line bg-panel/60 p-4">
        <svg viewBox="0 0 900 330" className="mx-auto min-w-[640px] w-full" role="img"
          aria-label="Pipeline: image, voice and message inputs each go through their own checks, produce signals, are fused into a score, then an explanation and next steps.">
          <defs>
            <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#22d3ee" /></marker>
          </defs>
          <Box x={10} y={20} w={120} h={60} title="Image" />
          <Box x={10} y={135} w={120} h={60} title="Voice" />
          <Box x={10} y={250} w={120} h={60} title="Message" />
          {arrow(130, 50, 170, 50)}{arrow(130, 165, 170, 165)}{arrow(130, 280, 170, 280)}
          <Box x={170} y={10} w={220} h={80} title="AI classifier + metadata" sub="ELA · frequency · heat map" />
          <Box x={170} y={125} w={220} h={80} title="Anti-spoof model" sub="pitch · pauses · noise · spectrum" />
          <Box x={170} y={240} w={220} h={80} title="Scam rules + link checks" sub="optional AI re-read" />
          {arrow(390, 50, 430, 150)}{arrow(390, 165, 430, 165)}{arrow(390, 280, 430, 180)}
          <Box x={430} y={125} w={150} h={80} title="Signals" sub="measured, with weights" tone="#16314a" />
          {arrow(580, 165, 620, 165)}
          <Box x={620} y={125} w={130} h={80} title="Fusion" sub="score · confidence" tone="#16314a" />
          {arrow(750, 165, 780, 165)}
          <Box x={780} y={95} w={110} h={60} title="Explanation" sub="from signals only" tone="#1a3a3a" />
          <Box x={780} y={175} w={110} h={60} title="Next steps" sub="what to do" tone="#1a3a3a" />
        </svg>
        <figcaption className="mt-2 text-center text-xs text-slate-400">In Combined mode, each score is merged with a bonus only when the pieces fit one scam story.</figcaption>
      </figure>

      <div className="grid gap-4 lg:grid-cols-3">
        {CHECKS.map((c) => (
          <article key={c.title} className="flex flex-col rounded-2xl border border-line bg-panel/70 p-5">
            <h3 className="text-lg font-bold"><span aria-hidden="true">{c.icon}</span> {c.title}</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">{c.does.map((d) => <li key={d}>{d}</li>)}</ul>
            <p className="mt-auto pt-4 text-sm text-amber-200"><strong>Limit:</strong> {c.cannot}</p>
          </article>
        ))}
      </div>

      <div className="rounded-2xl border border-line bg-panel/70 p-5 text-sm text-slate-300">
        <h3 className="mb-2 text-base font-bold text-slate-100">Honesty rules we follow</h3>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>We say “likelihood”, never “100% fake” or “100% real”.</li>
          <li>Every signal shown was measured or matched. If a check could not run, it is left out and listed under limitations.</li>
          <li>The written explanation may only mention facts that appear in the signal list; ungrounded sentences are dropped.</li>
          <li>Confidence is shown separately from risk, and drops for short, noisy, tiny or conflicting inputs.</li>
          <li>Files are analysed in memory and deleted straight away. History keeps only verdict summaries, in your browser.</li>
        </ul>
      </div>
    </section>
  );
}
