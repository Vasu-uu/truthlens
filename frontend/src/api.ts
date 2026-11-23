import type { AnalysisResult, SampleInfo } from "./types";

export const API: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function parse(r: Response): Promise<AnalysisResult> {
  let body: unknown = null;
  try {
    body = await r.json();
  } catch {
    /* non-JSON error body */
  }
  if (!r.ok) {
    const b = body as { code?: string; message?: string; detail?: unknown } | null;
    throw new ApiError(b?.code ?? "http_" + r.status, b?.message ?? "The server could not analyse this input.");
  }
  return body as AnalysisResult;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(API + path, init);
  } catch {
    throw new ApiError("backend_offline", `Cannot reach the TruthLens backend at ${API}. Is it running?`);
  }
}

export async function analyzeMessage(text: string, senderHint?: string): Promise<AnalysisResult> {
  return parse(
    await request("/api/analyze/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, sender_hint: senderHint || null }),
    }),
  );
}

export async function analyzeFile(kind: "image" | "audio", file: Blob, name: string): Promise<AnalysisResult> {
  const fd = new FormData();
  fd.append("file", file, name);
  return parse(await request(`/api/analyze/${kind}`, { method: "POST", body: fd }));
}

export async function analyzeCombined(p: { image?: File; audio?: File; text?: string }): Promise<AnalysisResult> {
  const fd = new FormData();
  if (p.image) fd.append("image", p.image, p.image.name);
  if (p.audio) fd.append("audio", p.audio, p.audio.name);
  if (p.text) fd.append("text", p.text);
  return parse(await request("/api/analyze/combined", { method: "POST", body: fd }));
}

export async function listSamples(): Promise<SampleInfo[]> {
  const r = await request("/api/samples");
  if (!r.ok) throw new ApiError("samples_failed", "Could not load the samples.");
  return (await r.json()) as SampleInfo[];
}

export const sampleFileUrl = (id: string): string => `${API}/api/samples/${id}/file`;

export async function analyzeSample(id: string): Promise<AnalysisResult> {
  return parse(await request(`/api/analyze/sample/${id}`, { method: "POST" }));
}

export async function fetchSampleFile(id: string, name: string, type: string): Promise<File> {
  const r = await request(`/api/samples/${id}/file`);
  if (!r.ok) throw new ApiError("sample_file", "Could not load the sample file.");
  return new File([await r.blob()], name, { type });
}

export async function health(): Promise<{ status: string; device: string }> {
  const r = await request("/api/health");
  return (await r.json()) as { status: string; device: string };
}
