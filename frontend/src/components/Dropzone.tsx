import { useEffect, useRef, useState } from "react";

interface Props {
  kind: "image" | "audio";
  file: File | null;
  onFile: (f: File | null) => void;
  label?: string;
}

const ACCEPT = { image: "image/jpeg,image/png,image/webp,image/heic,.heic", audio: "audio/*,.opus,.ogg,.m4a,.mp3,.wav" };
const MAX_MB = { image: 10, audio: 15 };

export default function Dropzone({ kind, file, onFile, label }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  const take = (f: File | undefined) => {
    if (!f) return;
    if (f.size > MAX_MB[kind] * 1024 * 1024) {
      setErr(`That file is larger than ${MAX_MB[kind]} MB.`);
      return;
    }
    setErr(null);
    onFile(f);
  };

  const noun = kind === "image" ? "an image" : "a voice note";
  return (
    <div>
      {label && <p className="mb-2 text-sm font-medium text-slate-300">{label}</p>}
      <div
        role="button"
        tabIndex={0}
        aria-label={`Upload ${noun}. Drag and drop or press Enter to browse.`}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            input.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          take(e.dataTransfer.files[0]);
        }}
        className={`flex min-h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-5 text-center transition ${
          over ? "border-accent bg-cyan-400/10" : "border-line bg-panel/60 hover:border-slate-500"
        }`}
      >
        {file && url ? (
          kind === "image" ? (
            <img src={url} alt="Selected image preview" className="max-h-52 rounded-lg object-contain" />
          ) : (
            <audio src={url} controls className="w-full" aria-label="Preview of the selected recording" onClick={(e) => e.stopPropagation()} />
          )
        ) : (
          <>
            <span className="text-3xl" aria-hidden="true">{kind === "image" ? "🖼️" : "🎙️"}</span>
            <span className="text-sm text-slate-200">Drop {noun} here, or <span className="text-accent underline">browse</span></span>
            <span className="text-xs text-slate-400">
              {kind === "image" ? "JPG, PNG, WebP, HEIC · up to 10 MB" : "WAV, MP3, M4A, OGG, OPUS (WhatsApp voice notes work) · up to 15 MB"}
            </span>
          </>
        )}
        <input ref={input} type="file" hidden accept={ACCEPT[kind]} onChange={(e) => take(e.target.files?.[0])} />
      </div>
      {file && (
        <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
          <span className="truncate">{file.name} · {(file.size / 1024).toFixed(0)} KB</span>
          <button className="rounded px-2 py-1 text-slate-300 hover:bg-panel2" onClick={() => onFile(null)}>Remove</button>
        </div>
      )}
      {err && <p className="mt-2 text-sm text-red-300" role="alert">{err}</p>}
    </div>
  );
}
