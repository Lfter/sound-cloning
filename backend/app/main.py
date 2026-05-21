from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audio import AudioError
from .service import VoiceStudioService


DEFAULT_CORS_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173", "tauri://localhost")
router = APIRouter()


class CreateProjectPayload(BaseModel):
    name: str = Field(default="剪辑补录项目", max_length=120)


class SaveScriptPayload(BaseModel):
    text: str = Field(default="", max_length=40_000)
    voiceId: str = Field(default="", max_length=80)
    controls: Dict[str, Any] = Field(default_factory=dict)


class UpdateLinePayload(BaseModel):
    voiceId: Optional[str] = Field(default=None, max_length=80)
    controls: Optional[Dict[str, Any]] = None


class GeneratePayload(BaseModel):
    projectId: str = Field(min_length=1, max_length=80)
    lineIds: List[str] = Field(default_factory=list, max_length=500)


class ExportPayload(BaseModel):
    projectId: str = Field(min_length=1, max_length=80)
    name: str = Field(default="", max_length=120)


def _cors_origins() -> List[str]:
    configured = os.environ.get("VOICE_STUDIO_CORS_ORIGINS", "")
    if not configured.strip():
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def create_app(studio_service: Optional[VoiceStudioService] = None) -> FastAPI:
    app = FastAPI(title="Voice Patch Studio API", version="0.1.0")
    app.state.service = studio_service or VoiceStudioService()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


def get_service(request: Request) -> VoiceStudioService:
    return request.app.state.service


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc).strip("'"))


@router.get("/health")
def health(studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    return studio.health()


@router.get("/model-status")
def model_status(studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    return studio.model_status()


@router.post("/voices")
async def create_voice(
    file: UploadFile = File(...),
    name: str = Form(..., max_length=120),
    referenceText: str = Form("", max_length=4_000),
    language: str = Form("Chinese", max_length=40),
    consentNote: str = Form("", max_length=1_000),
    trimStartMs: int = Form(0, ge=0, le=600_000),
    trimDurationMs: int = Form(10_000, ge=1_000, le=60_000),
    studio: VoiceStudioService = Depends(get_service),
) -> Dict[str, Any]:
    suffix = Path(file.filename or "reference.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        return studio.create_voice(
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


@router.get("/voices")
def list_voices(studio: VoiceStudioService = Depends(get_service)) -> List[Dict[str, Any]]:
    return studio.list_voices()


@router.post("/projects")
def create_project(payload: CreateProjectPayload, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    return studio.create_project(payload.name)


@router.get("/projects")
def list_projects(studio: VoiceStudioService = Depends(get_service)) -> List[Dict[str, Any]]:
    return studio.list_projects()


@router.get("/projects/{project_id}")
def get_project(project_id: str, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.get_project(project_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.put("/projects/{project_id}/script")
def save_script(project_id: str, payload: SaveScriptPayload, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.save_script(project_id, payload.text, payload.voiceId, payload.controls)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.patch("/script-lines/{line_id}")
def update_script_line(line_id: str, payload: UpdateLinePayload, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.update_script_line(line_id, payload.voiceId, payload.controls)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/generate")
def generate(payload: GeneratePayload, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.start_generation(payload.projectId, payload.lineIds)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.get("/jobs/{job_id}")
def get_job(job_id: str, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.get_job(job_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/clips/{clip_id}/select")
def select_clip(clip_id: str, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.select_clip(clip_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.get("/clips/{clip_id}/audio")
def clip_audio(clip_id: str, studio: VoiceStudioService = Depends(get_service)) -> FileResponse:
    try:
        path = studio.clip_path(clip_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file is missing.")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@router.post("/export")
def export_project(payload: ExportPayload, studio: VoiceStudioService = Depends(get_service)) -> Dict[str, Any]:
    try:
        return studio.export_project(payload.projectId, payload.name)
    except KeyError as exc:
        raise _not_found(exc) from exc


app = create_app()
