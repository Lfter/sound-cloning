import type {
  ExportResult,
  GenerationControls,
  GenerationJob,
  ModelStatus,
  Project,
  ScriptLine,
  VoiceProfile
} from "./types";

// Vite can override the backend host for packaged or remote-debug builds.
const apiBaseFromEnv = (import.meta as ImportMeta & { readonly env?: Record<string, string | undefined> }).env?.VITE_API_BASE;

export const API_BASE = (apiBaseFromEnv || "http://127.0.0.1:8787").replace(/\/+$/, "");

export class ApiError extends Error {
  /** HTTP status code from the backend response. */
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // FormData must keep its browser-generated multipart boundary, so only JSON
  // requests receive an explicit Content-Type.
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers
    }
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const payload = await response.json();
      message = payload.detail ?? message;
    } catch {
      // Fall back to raw text for validation or proxy errors that are not JSON.
      const text = await response.text().catch(() => "");
      message = text || message;
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// Backend and model readiness used by the header.
export function getModelStatus(): Promise<ModelStatus> {
  return request<ModelStatus>("/model-status");
}

// Voice library endpoints back the left sidebar.
export function listVoices(): Promise<VoiceProfile[]> {
  return request<VoiceProfile[]>("/voices");
}

export function createVoice(payload: {
  file: File;
  name: string;
  referenceText: string;
  language: string;
  consentNote: string;
  trimStartMs: number;
  trimDurationMs: number;
}): Promise<VoiceProfile> {
  // Uploads use multipart form data because they include user audio files.
  const form = new FormData();
  form.append("file", payload.file);
  form.append("name", payload.name);
  form.append("referenceText", payload.referenceText);
  form.append("language", payload.language);
  form.append("consentNote", payload.consentNote);
  form.append("trimStartMs", String(payload.trimStartMs));
  form.append("trimDurationMs", String(payload.trimDurationMs));
  return request<VoiceProfile>("/voices", { method: "POST", body: form });
}

export function createProject(name: string): Promise<Project> {
  return request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) });
}

// Project payloads include script lines and generated clips.
export function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function getProject(projectId: string): Promise<Project> {
  return request<Project>(`/projects/${projectId}`);
}

export function saveScript(projectId: string, text: string, voiceId: string, controls: GenerationControls): Promise<Project> {
  return request<Project>(`/projects/${projectId}/script`, {
    method: "PUT",
    body: JSON.stringify({ text, voiceId, controls })
  });
}

export function updateLine(lineId: string, voiceId: string, controls: GenerationControls): Promise<ScriptLine> {
  return request<ScriptLine>(`/script-lines/${lineId}`, {
    method: "PATCH",
    body: JSON.stringify({ voiceId, controls })
  });
}

export function startGenerate(projectId: string, lineIds: string[] = []): Promise<GenerationJob> {
  // Empty lineIds asks the backend to generate every line in the project.
  return request<GenerationJob>("/generate", {
    method: "POST",
    body: JSON.stringify({ projectId, lineIds })
  });
}

export function getJob(jobId: string): Promise<GenerationJob> {
  return request<GenerationJob>(`/jobs/${jobId}`);
}

export function selectClip(clipId: string): Promise<void> {
  return request<void>(`/clips/${clipId}/select`, { method: "POST" });
}

export function exportProject(projectId: string, name = ""): Promise<ExportResult> {
  return request<ExportResult>("/export", {
    method: "POST",
    body: JSON.stringify({ projectId, name })
  });
}

export function audioUrl(path: string): string {
  // Audio URLs are relative in API payloads so the frontend can swap API_BASE.
  return `${API_BASE}${path}`;
}
