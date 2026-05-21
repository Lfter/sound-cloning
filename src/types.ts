export type ModelStatus = {
  backend: string;
  available: boolean;
  modelPath: string;
  message: string;
};

export type VoiceProfile = {
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
  speed: number;
  pitchSemitones: number;
  gainDb: number;
  emotionHint: string;
  pauseMs: number;
  seed: number | null;
  variants: number;
};

export type GeneratedClip = {
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
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  lines: ScriptLine[];
};

export type GenerationJob = {
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
  exportDir: string;
  manifestPath: string;
  files: string[];
  count: number;
};
