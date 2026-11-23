import type { Artifacts } from "../types";

export default function AudioPanel({ a, audioUrl }: { a: Artifacts; audioUrl?: string }) {
  const peaks = a.waveform_peaks ?? [];
  const n = peaks.length || 1;
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-200">The recording</h3>
      {audioUrl && <audio controls src={audioUrl} className="w-full" aria-label="Play the analysed recording" />}
      {peaks.length > 0 && (
        <svg viewBox={`0 0 ${n} 40`} preserveAspectRatio="none" className="h-16 w-full rounded-lg bg-panel2" role="img" aria-label="Waveform of the recording">
          {peaks.map((p, i) => (
            <rect key={i} x={i} y={20 - p * 19} width={0.7} height={Math.max(0.6, p * 38)} fill="#22d3ee" opacity={0.85} />
          ))}
        </svg>
      )}
      {a.spectrogram_png_base64 && (
        <figure className="m-0">
          <img src={`data:image/png;base64,${a.spectrogram_png_base64}`} alt="Mel spectrogram: time runs left to right, pitch bottom to top, brighter means louder" className="w-full rounded-lg border border-line" />
          <figcaption className="mt-1 text-xs text-slate-400">
            Spectrogram{a.duration_s ? ` · ${a.duration_s}s` : ""}. Brighter = louder. Natural voices show uneven texture and background noise; generated voices can look unusually clean or regular.
          </figcaption>
        </figure>
      )}
    </div>
  );
}
