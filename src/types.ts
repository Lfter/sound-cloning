// API contracts shared by React components and the backend JSON responses.

export type ModelStatus = {
  // `available` means the real model path and runtime dependency were detected.
  backend: string;
  available: boolean;
  modelPath: string;
  message: string;
  candidateModels: string[];
};

export type VoiceProfile = {
  // Voice records keep both the original import and the normalized prompt WAV.
  id: string;
  name: string;
  referenceAudioPath: string;
  promptAudioPath: string;
  referenceText: string;
  language: string;
  consentNote: string;
  modelPromptPath: string;
  createdAt: string;
};

export type GenerationControls = {
  // These limits are mirrored by backend validation before persistence/generation.
  speed: number;
  pitchSemitones: number;
  gainDb: number;
  emotionHint: string;
  pauseMs: number;
  seed: number | null;
  variants: number;
};

export type GeneratedClip = {
  // A line can have multiple generated candidates; one may be selected for export.
  id: string;
  projectId: string;
  scriptLineId: string;
  variantIndex: number;
  wavPath: string;
  audioUrl: string;
  durationMs: number;
  sampleRate: number;
  lufs: number;
  settingsSnapshot: Record<string, unknown>;
  createdAt: string;
};

export type ScriptLine = {
  // Script lines are the editable unit for per-line voice and control overrides.
  id: string;
  projectId: string;
  lineIndex: number;
  text: string;
  voiceId: string;
  controls: GenerationControls;
  selectedClipId: string;
  clips: GeneratedClip[];
};

export type Project = {
  // The project payload is hydrated with lines to avoid extra frontend round trips.
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  lines: ScriptLine[];
};

export type GenerationJob = {
  // Jobs are in-memory backend tasks polled by the frontend progress UI.
  id: string;
  projectId: string;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  total: number;
  message: string;
  clipIds: string[];
  errors: string[];
  createdAt: string;
  updatedAt: string;
};

export type ExportResult = {
  // Paths point to local files created under the configured export directory.
  exportDir: string;
  manifestPath: string;
  files: string[];
  count: number;
};
