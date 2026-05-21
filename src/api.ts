import type {
  ExportResult,
  GenerationControls,
  GenerationJob,
  ModelStatus,
  Project,
  ScriptLine,
  VoiceProfile
} from "./types";

export const API_BASE = "http://127.0.0.1:8787";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
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
      // Keep the HTTP status text when the server returns non-JSON errors.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getModelStatus(): Promise<ModelStatus> {
  return request<ModelStatus>("/model-status");
}

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
  return `${API_BASE}${path}`;
}
