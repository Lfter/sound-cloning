from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audio import AudioError
from .service import VoiceStudioService


app = FastAPI(title="Voice Patch Studio API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = VoiceStudioService()


class CreateProjectPayload(BaseModel):
    name: str = Field(default="剪辑补录项目")


class SaveScriptPayload(BaseModel):
    text: str
    voiceId: str = ""
    controls: Dict[str, Any] = Field(default_factory=dict)


class UpdateLinePayload(BaseModel):
    voiceId: Optional[str] = None
    controls: Optional[Dict[str, Any]] = None


class GeneratePayload(BaseModel):
    projectId: str
    lineIds: List[str] = Field(default_factory=list)


class ExportPayload(BaseModel):
    projectId: str
    name: str = ""


@app.get("/health")
def health() -> Dict[str, Any]:
    return service.health()


@app.get("/model-status")
def model_status() -> Dict[str, Any]:
    return service.model_status()


@app.post("/voices")
async def create_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    referenceText: str = Form(""),
    language: str = Form("Chinese"),
    consentNote: str = Form(""),
    trimStartMs: int = Form(0),
    trimDurationMs: int = Form(10_000),
) -> Dict[str, Any]:
    suffix = Path(file.filename or "reference.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        return service.create_voice(
            name=name,
            source_audio_path=tmp_path,
            original_filename=file.filename or "reference.wav",
            reference_text=referenceText,
            language=language,
            consent_note=consentNote,
            trim_start_ms=trimStartMs,
            trim_duration_ms=trimDurationMs,
        )
    except AudioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/voices")
def list_voices() -> List[Dict[str, Any]]:
    return service.list_voices()


@app.post("/projects")
def create_project(payload: CreateProjectPayload) -> Dict[str, Any]:
    return service.create_project(payload.name)


@app.get("/projects")
def list_projects() -> List[Dict[str, Any]]:
    return service.list_projects()


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    try:
        return service.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/projects/{project_id}/script")
def save_script(project_id: str, payload: SaveScriptPayload) -> Dict[str, Any]:
    try:
        return service.save_script(project_id, payload.text, payload.voiceId, payload.controls)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/script-lines/{line_id}")
def update_script_line(line_id: str, payload: UpdateLinePayload) -> Dict[str, Any]:
    try:
        return service.update_script_line(line_id, payload.voiceId, payload.controls)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/generate")
def generate(payload: GeneratePayload) -> Dict[str, Any]:
    try:
        return service.start_generation(payload.projectId, payload.lineIds)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    try:
        return service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/clips/{clip_id}/select")
def select_clip(clip_id: str) -> Dict[str, Any]:
    try:
        return service.select_clip(clip_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/clips/{clip_id}/audio")
def clip_audio(clip_id: str) -> FileResponse:
    try:
        path = service.clip_path(clip_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file is missing.")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@app.post("/export")
def export_project(payload: ExportPayload) -> Dict[str, Any]:
    try:
        return service.export_project(payload.projectId, payload.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
