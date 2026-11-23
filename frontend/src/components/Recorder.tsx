import { useEffect, useRef, useState } from "react";
import { useToast } from "./Toasts";

/** Records from the microphone with MediaRecorder and hands back a File. */
export default function Recorder({ onFile }: { onFile: (f: File) => void }) {
  const toast = useToast();
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | null>(null);
  const [on, setOn] = useState(false);
  const [secs, setSecs] = useState(0);

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  const start = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      toast("Recording is not supported in this browser. Upload a file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(stream);
      chunks.current = [];
      r.ondataavailable = (e) => { if (e.data.size) chunks.current.push(e.data); };
      r.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const type = r.mimeType || "audio/webm";
        const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
        onFile(new File(chunks.current, `recording.${ext}`, { type }));
      };
      r.start();
      rec.current = r;
      setSecs(0);
      setOn(true);
      timer.current = window.setInterval(() => setSecs((s) => {
        if (s >= 59) { r.stop(); return s; }
        return s + 1;
      }), 1000);
    } catch {
      toast("Microphone access was blocked or no microphone was found.");
    }
  };

  const stop = () => {
    rec.current?.stop();
    if (timer.current) window.clearInterval(timer.current);
    setOn(false);
  };

  return (
    <div className="flex items-center gap-3">
      {on ? (
        <button onClick={stop} className="inline-flex items-center gap-2 rounded-xl bg-red-500/90 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-white" aria-hidden="true" /> Stop · {secs}s
        </button>
      ) : (
        <button onClick={start} className="inline-flex items-center gap-2 rounded-xl border border-line bg-panel2 px-4 py-2 text-sm font-medium hover:border-slate-500">
          <span aria-hidden="true">⏺</span> Record from microphone
        </button>
      )}
      <span className="text-xs text-slate-400" aria-live="polite">{on ? "Recording… up to 60 s" : "Or record a short clip (calls on speaker work too)"}</span>
    </div>
  );
}
