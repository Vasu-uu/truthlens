import { useEffect, useState } from "react";
import { ApiError, analyzeCombined, analyzeSample, fetchSampleFile, listSamples, sampleFileUrl } from "../api";
import type { AnalysisResult, Media, SampleInfo } from "../types";
import { useToast } from "./Toasts";

interface Props {
  onResult: (r: AnalysisResult, m: Media) => void;
  busy: boolean;
  setBusy: (b: boolean) => void;
}

const GROUPS: { id: SampleInfo["modality"]; title: string; icon: string }[] = [
  { id: "message", title: "Messages", icon: "💬" },
  { id: "audio", title: "Voice notes", icon: "🎙️" },
  { id: "image", title: "Images", icon: "🖼️" },
];
const EXPECT: Record<string, string> = {
  scam: "Known scam", legit: "Genuine", real: "Real photo/voice", ai: "AI-generated", synthetic: "Synthetic voice",
};

export default function Samples({ onResult, busy, setBusy }: Props) {
  const toast = useToast();
  const [list, setList] = useState<SampleInfo[] | null>(null);

  useEffect(() => {
    listSamples().then(setList).catch((e) => {
      setList([]);
      toast(e instanceof ApiError ? e.message : "Could not load samples.");
    });
  }, [toast]);

  const run = async (s: SampleInfo) => {
    setBusy(true);
    try {
      const r = await analyzeSample(s.id);
      const m: Media = {};
      if (s.modality === "message") m.text = s.text;
      if (s.modality === "image") m.imageUrl = sampleFileUrl(s.id);
      if (s.modality === "audio") m.audioUrl = sampleFileUrl(s.id);
      onResult(r, m);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not analyse this sample.");
    } finally {
      setBusy(false);
    }
  };

  const demo = async () => {
    if (!list) return;
    const msg = list.find((s) => s.id === "msg-scam-son-in-trouble");
    const aud = list.find((s) => s.modality === "audio" && s.expected === "synthetic");
    const img = list.find((s) => s.modality === "image" && s.expected === "ai") ?? list.find((s) => s.modality === "image");
    setBusy(true);
    try {
      const [audio, image] = await Promise.all([
        aud ? fetchSampleFile(aud.id, "voice.wav", "audio/wav") : Promise.resolve(undefined),
        img ? fetchSampleFile(img.id, "photo.jpg", "image/jpeg") : Promise.resolve(undefined),
      ]);
      const r = await analyzeCombined({ audio, image, text: msg?.text });
      onResult(r, { text: msg?.text, audioUrl: aud ? sampleFileUrl(aud.id) : undefined, imageUrl: img ? sampleFileUrl(img.id) : undefined });
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not run the demo.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="Sample gallery" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-cyan-400/30 bg-cyan-400/5 p-4">
        <div>
          <h2 className="font-bold">Try the “son in trouble” scam</h2>
          <p className="text-sm text-slate-300">A panicked message asking for UPI money, plus a synthetic voice and a photo, checked together.</p>
        </div>
        <button onClick={demo} disabled={busy || !list?.length} className="rounded-xl bg-accent px-5 py-2.5 text-sm font-bold text-slate-950 disabled:opacity-40">
          Run combined demo
        </button>
      </div>

      {list === null && <div className="skeleton h-40" />}
      {GROUPS.map((g) => {
        const items = (list ?? []).filter((s) => s.modality === g.id);
        if (!items.length) return null;
        return (
          <div key={g.id}>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400"><span aria-hidden="true">{g.icon}</span> {g.title}</h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((s) => (
                <li key={s.id} className="flex flex-col gap-3 rounded-2xl border border-line bg-panel/70 p-4">
                  {s.modality === "image" && <img src={sampleFileUrl(s.id)} alt={s.title} loading="lazy" className="h-32 w-full rounded-lg object-cover" />}
                  {s.modality === "audio" && <audio controls src={sampleFileUrl(s.id)} className="w-full" aria-label={`Play ${s.title}`} />}
                  {s.modality === "message" && <p className="line-clamp-4 text-sm text-slate-300">“{s.text}”</p>}
                  <div className="mt-auto flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{s.title}</p>
                      <p className="text-xs text-slate-400">Source label: {EXPECT[s.expected] ?? s.expected}</p>
                    </div>
                    <button onClick={() => run(s)} disabled={busy} className="shrink-0 rounded-lg border border-accent px-3 py-1.5 text-xs font-bold text-accent hover:bg-cyan-400/10 disabled:opacity-40">
                      Analyse
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <p className="text-xs text-slate-500">“Source label” is where the sample came from, not TruthLens’s verdict. Add your own examples in <code>backend/samples/</code>.</p>
    </section>
  );
}
