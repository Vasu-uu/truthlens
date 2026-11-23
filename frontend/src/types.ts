export type Level = "low" | "medium" | "high";
export type Modality = "image" | "audio" | "message" | "combined";

export interface Signal {
  id: string;
  name: string;
  category: "image" | "audio" | "message" | "url" | "cross-modal";
  value: string | number | boolean | null;
  direction: "suspicious" | "reassuring" | "neutral";
  weight: number;
  detail: string;
}

export interface Highlight {
  start: number;
  end: number;
  tactic: string;
  signal_id: string;
}

export interface Entities {
  upi_ids: string[];
  urls: string[];
  phone_numbers: string[];
  amounts: string[];
}

export interface PerModality {
  modality: Modality;
  risk_score: number;
  risk_level: Level;
  confidence: Level;
  headline: string;
}

/** Artifacts differ by modality; fields are optional and read defensively. */
export interface Artifacts {
  heatmap_png_base64?: string;
  heatmap_method?: string;
  ela_png_base64?: string;
  original_png_base64?: string;
  spectrogram_png_base64?: string;
  waveform_peaks?: number[];
  duration_s?: number;
  scam_type?: string | null;
  scam_type_label?: string;
  entities?: Entities;
  highlights?: Highlight[];
  tactics?: string[];
  explanation_source?: string;
  per_modality?: PerModality[];
  cross_modal_bonus?: number;
  cross_modal_reason?: string | null;
  parts?: Partial<Record<Modality, { artifacts: Artifacts; explanation: string }>>;
  [key: string]: unknown;
}

export interface AnalysisResult {
  modality: Modality;
  risk_score: number;
  risk_level: Level;
  confidence: Level;
  headline: string;
  signals: Signal[];
  explanation: string;
  next_steps: string[];
  artifacts: Artifacts;
  limitations: string[];
  processing_ms: number;
  model_versions: Record<string, string>;
}

/** What the user submitted, kept client-side only for display. */
export interface Media {
  imageUrl?: string;
  audioUrl?: string;
  text?: string;
}

export interface SampleInfo {
  id: string;
  modality: "image" | "audio" | "message";
  title: string;
  expected: string;
  text?: string;
}
