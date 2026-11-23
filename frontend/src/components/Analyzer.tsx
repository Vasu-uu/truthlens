import { useEffect, useState } from "react";
import { ApiError, analyzeCombined, analyzeFile, analyzeMessage } from "../api";
import type { AnalysisResult, Media } from "../types";
import Dropzone from "./Dropzone";
import Recorder from "./Recorder";
import { useToast } from "./Toasts";

type Tab = "image" | "audio" | "message" | "combined";
const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "image", label: "Image", icon: "🖼️" },
  { id: "audio", label: "Voice", icon: "🎙️" },
  { id: "message", label: "Message", icon: "💬" },
  { id: "combined", label: "Combined", icon: "🧩" },
];
const STEPS: Record<Tab, string[]> = {
  image: ["Reading metadata", "Running the AI-image detector", "Checking error levels and noise", "Drawing the attention map"],
  audio: ["Decoding the audio", "Running the voice detector", "Measuring pitch, pauses and noise", "Drawing the spectrogram"],
  message: ["Scanning for scam patterns", "Checking links", "Writing the explanation"],
  combined: ["Analysing each item", "Looking for a matching scam story", "Writing the explanation"],
};
const SENDERS = ["", "WhatsApp", "SMS", "Email", "Instagram / DM", "Unknown number"];

interface Props {
  onResult: (r: AnalysisResult, m: Media) => void;
  busy: boolean;
  setBusy: (b: boolean) => void;
  initialTab?: Tab;
}

export default function Analyzer({ onResult, busy, setBusy, initialTab = "message" }: Props) {
  const toast = useToast();
  const [tab, setTab] = useState<Tab>(initialTab);
  const [image, setImage] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [sender, setSender] = useState("");
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!busy) return;
    setStep(0);
    const t = window.setInterval(() => setStep((s) => Math.min(s + 1, STEPS[tab].length - 1)), 1800);
    return () => window.clearInterval(t);
  }, [busy, tab]);

  const ready =
    (tab === "image" && !!image) || (tab === "audio" && !!audio) || (tab === "message" && text.trim().length > 0) ||
    (tab === "combined" && (!!image || !!audio || text.trim().length > 0));

  const run = async () => {
    setBusy(true);
    try {
      let r: AnalysisResult;
      const media: Media = {};
      if (tab === "image" && image) {
        r = await analyzeFile("image", image, image.name);
        media.imageUrl = URL.createObjectURL(image);
      } else if (tab === "audio" && audio) {
        r = await analyzeFile("audio", audio, audio.name);
        media.audioUrl = URL.createObjectURL(audio);
      } else if (tab === "message") {
        r = await analyzeMessage(text, sender);
        media.text = text.trim();
      } else {
        r = await analyzeCombined({ image: image ?? undefined, audio: audio ?? undefined, text: text.trim() || undefined });
        if (image) media.imageUrl = URL.createObjectURL(image);
        if (audio) media.audioUrl = URL.createObjectURL(audio);
        if (text.trim()) media.text = text.trim();
      }
      onResult(r, media);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const messageBox = (
    <div>
      <label htmlFor="msg" className="mb-2 block text-sm font-medium text-slate-300">
        Paste the message (SMS, WhatsApp, email, DM)
      </label>
      <textarea
        id="msg"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={5000}
        rows={tab === "combined" ? 4 : 7}
        placeholder="e.g. Mom I changed my number. I'm in trouble, please send Rs 25,000 urgently to…"
        className="w-full resize-y rounded-2xl border border-line bg-panel/60 p-4 text-sm leading-relaxed placeholder:text-slate-500 focus:border-accent"
      />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <label className="flex items-center gap-2">
          Where did it arrive?
          <select value={sender} onChange={(e) => setSender(e.target.value)} className="rounded-lg border border-line bg-panel2 px-2 py-1 text-slate-200">
            {SENDERS.map((s) => <option key={s} value={s}>{s || "Not sure"}</option>)}
          </select>
        </label>
        <span>{text.length}/5000</span>
      </div>
    </div>
  );

  return (
    <section aria-label="Analyzer" className="rounded-3xl border border-line bg-panel/70 p-4 shadow-2xl backdrop-blur sm:p-6">
      <div role="tablist" aria-label="What do you want to check?" className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="tabpanel"
            onClick={() => setTab(t.id)}
            onKeyDown={(e) => {
              const i = TABS.findIndex((x) => x.id === tab);
              if (e.key === "ArrowRight") setTab(TABS[(i + 1) % TABS.length].id);
              if (e.key === "ArrowLeft") setTab(TABS[(i + TABS.length - 1) % TABS.length].id);
            }}
            tabIndex={tab === t.id ? 0 : -1}
            className={`flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${
              tab === t.id ? "border-accent bg-cyan-400/10 text-white" : "border-line text-slate-300 hover:bg-panel2"
            }`}
          >
            <span aria-hidden="true">{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      <div id="tabpanel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="space-y-4">
        {busy ? (
          <div aria-busy="true" aria-live="polite" className="space-y-3 py-2">
            <p className="text-sm text-cyan-200">{STEPS[tab][step]}…</p>
            <div className="skeleton h-28 w-full" />
            <div className="grid grid-cols-3 gap-3"><div className="skeleton h-16" /><div className="skeleton h-16" /><div className="skeleton h-16" /></div>
          </div>
        ) : (
          <>
            {tab === "image" && <Dropzone kind="image" file={image} onFile={setImage} />}
            {tab === "audio" && (
              <>
                <Dropzone kind="audio" file={audio} onFile={setAudio} />
                <Recorder onFile={setAudio} />
              </>
            )}
            {tab === "message" && messageBox}
            {tab === "combined" && (
              <>
                <p className="text-sm text-slate-300">Add whatever you received, for example a voice note, a photo and a message about the same “emergency”. TruthLens checks whether they fit one scam story.</p>
                <div className="grid gap-4 md:grid-cols-2">
                  <Dropzone kind="image" file={image} onFile={setImage} label="Photo (optional)" />
                  <div className="space-y-3">
                    <Dropzone kind="audio" file={audio} onFile={setAudio} label="Voice note (optional)" />
                    <Recorder onFile={setAudio} />
                  </div>
                </div>
                {messageBox}
              </>
            )}
          </>
        )}
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-md text-xs text-slate-400">
          🔒 Files are analysed in memory and deleted right after. Nothing is stored on the server, and results stay in your browser.
        </p>
        <button
          onClick={run}
          disabled={!ready || busy}
          className="rounded-xl bg-accent px-6 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Analysing…" : "Analyse"}
        </button>
      </div>
    </section>
  );
}
