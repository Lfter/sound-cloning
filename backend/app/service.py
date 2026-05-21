"""Core application service for voices, projects, generation jobs, and exports."""

from __future__ import annotations

import csv
import json
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .audio import AudioError, convert_reference_audio, duration_ms, estimate_lufs
from .config import DEFAULT_LANGUAGE, DEFAULT_REFERENCE_DURATION_MS, StudioPaths
from .database import Database, json_loads
from .qwen_adapter import Qwen3TTSAdapter, copy_export_clip
from .script import safe_filename, split_script
from .types import GenerationControls, GeneratedClip, ScriptLine, VoiceProfile


def now_iso() -> str:
    """Return an ISO timestamp in UTC for API and database records."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class GenerationJob:
    """In-memory representation of a generation task shown to the frontend."""

    id: str
    project_id: str
    status: str = "queued"
    progress: int = 0
    total: int = 0
    message: str = ""
    clip_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_api(self) -> Dict[str, Any]:
        """Convert internal snake_case fields to the frontend API shape."""

        return {
            "id": self.id,
            "projectId": self.project_id,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "message": self.message,
            "clipIds": self.clip_ids,
            "errors": self.errors,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class JobStore:
    """Thread-safe in-memory job registry for the current backend process."""

    def __init__(self) -> None:
        self._jobs: Dict[str, GenerationJob] = {}
        self._lock = threading.Lock()

    def create(self, project_id: str) -> GenerationJob:
        """Create a queued job for a project."""

        job = GenerationJob(id=str(uuid.uuid4()), project_id=project_id)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[GenerationJob]:
        """Fetch a job if it is still tracked by this process."""

        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: Any) -> GenerationJob:
        """Patch job fields while keeping updated_at fresh."""

        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = now_iso()
            return job


class VoiceStudioService:
    """Business layer shared by FastAPI routes and unit tests."""

    def __init__(self, paths: Optional[StudioPaths] = None):
        self.paths = paths or StudioPaths.from_env()
        self.paths.ensure()
        self.db = Database(self.paths.db_path)
        self.adapter = Qwen3TTSAdapter(self.paths)
        self.jobs = JobStore()

    def health(self) -> Dict[str, Any]:
        """Expose runtime paths and model availability for startup checks."""

        return {
            "ok": True,
            "dataDir": str(self.paths.data_dir),
            "modelsDir": str(self.paths.models_dir),
            "model": self.adapter.status().to_api(),
        }

    def model_status(self) -> Dict[str, Any]:
        """Return the current model adapter status."""

        return self.adapter.status().to_api()

    def create_voice(
        self,
        name: str,
        source_audio_path: Path,
        original_filename: str,
        reference_text: str,
        language: str = DEFAULT_LANGUAGE,
        consent_note: str = "",
        trim_start_ms: int = 0,
        trim_duration_ms: int = DEFAULT_REFERENCE_DURATION_MS,
    ) -> Dict[str, Any]:
        """Import a reference recording and register it as a reusable voice."""

        name = name.strip() or "Untitled Voice"
        voice_id = str(uuid.uuid4())
        voice_folder = self.paths.original_voice_dir / voice_id
        voice_folder.mkdir(parents=True, exist_ok=True)
        suffix = Path(original_filename or source_audio_path.name).suffix or ".wav"
        original_path = voice_folder / f"reference{suffix.lower()}"
        prompt_path = self.paths.prompt_voice_dir / f"{voice_id}.wav"
        shutil.copyfile(source_audio_path, original_path)
        convert_reference_audio(original_path, prompt_path, trim_start_ms, trim_duration_ms)

        created_at = now_iso()
        self.db.execute(
            """
            INSERT INTO voices (
              id, name, reference_audio_path, prompt_audio_path, reference_text,
              language, consent_note, model_prompt_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                voice_id,
                name,
                str(original_path),
                str(prompt_path),
                reference_text.strip(),
                language or DEFAULT_LANGUAGE,
                consent_note.strip(),
                "",
                created_at,
            ),
        )
        return self.get_voice(voice_id)

    def get_voice(self, voice_id: str) -> Dict[str, Any]:
        """Return one voice profile or raise KeyError for API 404 handling."""

        row = self.db.query_one("SELECT * FROM voices WHERE id = ?", (voice_id,))
        if not row:
            raise KeyError(f"Voice not found: {voice_id}")
        return _voice_row_to_api(row)

    def list_voices(self) -> List[Dict[str, Any]]:
        """List voices newest first for the sidebar."""

        rows = self.db.query_all("SELECT * FROM voices ORDER BY created_at DESC")
        return [_voice_row_to_api(row) for row in rows]

    def create_project(self, name: str) -> Dict[str, Any]:
        """Create an empty editing project."""

        project_id = str(uuid.uuid4())
        timestamp = now_iso()
        self.db.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (project_id, name.strip() or "剪辑补录项目", timestamp, timestamp),
        )
        return self.get_project(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        """List projects by last update so recent work stays on top."""

        rows = self.db.query_all("SELECT * FROM projects ORDER BY updated_at DESC")
        return [_project_row_to_api(row) for row in rows]

    def get_project(self, project_id: str) -> Dict[str, Any]:
        """Load a project with its script lines and generated clip candidates."""

        project = self.db.query_one("SELECT * FROM projects WHERE id = ?", (project_id,))
        if not project:
            raise KeyError(f"Project not found: {project_id}")
        lines = self.db.query_all(
            "SELECT * FROM script_lines WHERE project_id = ? ORDER BY line_index ASC",
            (project_id,),
        )
        clips = self.db.query_all(
            "SELECT * FROM clips WHERE project_id = ? ORDER BY script_line_id ASC, variant_index ASC",
            (project_id,),
        )
        clips_by_line: Dict[str, List[Dict[str, Any]]] = {}
        for clip in clips:
            clips_by_line.setdefault(clip["script_line_id"], []).append(_clip_row_to_api(clip))
        api_lines = []
        for line in lines:
            # Clip rows are grouped in memory to avoid repeated database calls per line.
            line_api = _line_row_to_api(line)
            line_api["clips"] = clips_by_line.get(line["id"], [])
            api_lines.append(line_api)
        result = _project_row_to_api(project)
        result["lines"] = api_lines
        return result

    def save_script(
        self,
        project_id: str,
        script_text: str,
        voice_id: str = "",
        controls: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Replace a project's script and clear stale generated clips."""

        if not self.db.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
            raise KeyError(f"Project not found: {project_id}")
        default_voice_id = voice_id or _first_voice_id(self.db) or ""
        default_controls = GenerationControls.from_dict(controls).to_json()
        lines = split_script(script_text)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM clips WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM script_lines WHERE project_id = ?", (project_id,))
            for index, text in enumerate(lines, start=1):
                conn.execute(
                    """
                    INSERT INTO script_lines (
                      id, project_id, line_index, text, voice_id, controls_json, selected_clip_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), project_id, index, text, default_voice_id, default_controls, ""),
                )
            conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_iso(), project_id))
        return self.get_project(project_id)

    def update_script_line(
        self,
        line_id: str,
        voice_id: Optional[str] = None,
        controls: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update per-line voice and generation controls without rewriting text."""

        row = self.db.query_one("SELECT * FROM script_lines WHERE id = ?", (line_id,))
        if not row:
            raise KeyError(f"Line not found: {line_id}")
        next_voice_id = row["voice_id"] if voice_id is None else voice_id
        current_controls = json_loads(row["controls_json"])
        if controls is not None:
            current_controls.update(controls)
        next_controls = GenerationControls.from_dict(current_controls).to_json()
        self.db.execute(
            "UPDATE script_lines SET voice_id = ?, controls_json = ? WHERE id = ?",
            (next_voice_id, next_controls, line_id),
        )
        next_row = self.db.query_one("SELECT * FROM script_lines WHERE id = ?", (line_id,))
        assert next_row is not None
        return _line_row_to_api(next_row)

    def start_generation(self, project_id: str, line_ids: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """Start background generation for a whole project or selected lines."""

        if not self.db.query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
            raise KeyError(f"Project not found: {project_id}")
        job = self.jobs.create(project_id)
        requested_ids = list(line_ids or [])
        thread = threading.Thread(target=self._run_generation_job, args=(job.id, requested_ids), daemon=True)
        thread.start()
        return job.to_api()

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Return public job state for polling."""

        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        return job.to_api()

    def select_clip(self, clip_id: str) -> Dict[str, Any]:
        """Mark one generated candidate as the export choice for its line."""

        clip = self.db.query_one("SELECT * FROM clips WHERE id = ?", (clip_id,))
        if not clip:
            raise KeyError(f"Clip not found: {clip_id}")
        self.db.execute(
            "UPDATE script_lines SET selected_clip_id = ? WHERE id = ?",
            (clip_id, clip["script_line_id"]),
        )
        return _clip_row_to_api(clip)

    def clip_path(self, clip_id: str) -> Path:
        """Resolve a clip id to its WAV file on disk."""

        clip = self.db.query_one("SELECT wav_path FROM clips WHERE id = ?", (clip_id,))
        if not clip:
            raise KeyError(f"Clip not found: {clip_id}")
        return Path(clip["wav_path"])

    def export_project(self, project_id: str, export_name: str = "") -> Dict[str, Any]:
        """Copy selected clips into an export folder and write a CSV manifest."""

        project = self.get_project(project_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = export_name.strip() or f"{project['name']}_{timestamp}"
        safe_folder = "".join(ch for ch in folder_name if ch not in '\\/:*?"<>|').strip() or f"export_{timestamp}"
        export_dir = _unique_dir(self.paths.export_dir / safe_folder)
        export_dir.mkdir(parents=True, exist_ok=True)

        manifest_rows = []
        exported_files: List[str] = []
        voices = {voice["id"]: voice for voice in self.list_voices()}
        for line in project["lines"]:
            clip = _preferred_clip(line)
            if not clip:
                continue
            # Export filenames are stable and editor-friendly: line number plus text.
            target_name = safe_filename(line["lineIndex"], line["text"])
            target = export_dir / target_name
            copy_export_clip(Path(clip["wavPath"]), target)
            exported_files.append(str(target))
            controls = line["controls"]
            voice = voices.get(line["voiceId"], {})
            manifest_rows.append(
                {
                    "index": line["lineIndex"],
                    "text": line["text"],
                    "voice": voice.get("name", ""),
                    "speed": controls["speed"],
                    "pitch_semitones": controls["pitchSemitones"],
                    "gain_db": controls["gainDb"],
                    "emotion_hint": controls["emotionHint"],
                    "pause_ms": controls["pauseMs"],
                    "seed": controls["seed"] or "",
                    "variant": clip["variantIndex"],
                    "duration_ms": clip["durationMs"],
                    "lufs": clip["lufs"],
                    "file": target_name,
                    "source_clip": clip["wavPath"],
                }
            )

        manifest_path = export_dir / "manifest.csv"
        with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "index",
                    "text",
                    "voice",
                    "speed",
                    "pitch_semitones",
                    "gain_db",
                    "emotion_hint",
                    "pause_ms",
                    "seed",
                    "variant",
                    "duration_ms",
                    "lufs",
                    "file",
                    "source_clip",
                ],
            )
            writer.writeheader()
            writer.writerows(manifest_rows)

        return {
            "exportDir": str(export_dir),
            "manifestPath": str(manifest_path),
            "files": exported_files,
            "count": len(exported_files),
        }

    def _run_generation_job(self, job_id: str, requested_ids: List[str]) -> None:
        """Worker entrypoint that keeps partial progress even if one line fails."""

        job = self.jobs.get(job_id)
        if job is None:
            return
        line_filter = set(requested_ids)
        rows = self.db.query_all(
            "SELECT * FROM script_lines WHERE project_id = ? ORDER BY line_index ASC",
            (job.project_id,),
        )
        if line_filter:
            rows = [row for row in rows if row["id"] in line_filter]
        total = sum(GenerationControls.from_dict(json_loads(row["controls_json"])).validated().variants for row in rows)
        self.jobs.update(job_id, status="running", total=total, message="Preparing generation")

        clip_ids: List[str] = []
        errors: List[str] = []
        progress = 0
        for row in rows:
            try:
                clip_ids.extend(self._generate_line(row, job_id, progress, clip_ids, errors))
            except Exception as exc:  # noqa: BLE001 - keep batch jobs moving.
                errors.append(f"Line {row['line_index']}: {exc}")
            progress = len(clip_ids)
            self.jobs.update(job_id, progress=progress, clip_ids=clip_ids, errors=errors)

        status = "done" if not errors else "error"
        message = "Finished" if not errors else "Finished with errors"
        self.jobs.update(job_id, status=status, message=message, clip_ids=clip_ids, errors=errors)

    def _generate_line(
        self,
        row: Dict[str, Any],
        job_id: Optional[str] = None,
        completed_before_line: int = 0,
        prior_clip_ids: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
    ) -> List[str]:
        """Generate all variants for a single script line and persist clip rows."""

        line = _line_row_to_dataclass(row)
        if not line.voice_id:
            raise ValueError("No voice selected.")
        voice_row = self.db.query_one("SELECT * FROM voices WHERE id = ?", (line.voice_id,))
        if not voice_row:
            raise ValueError("Selected voice no longer exists.")
        voice = _voice_row_to_dataclass(voice_row)
        controls = line.controls.validated()
        line_dir = self.paths.clip_dir / line.project_id / f"{line.line_index:03d}"
        line_dir.mkdir(parents=True, exist_ok=True)

        with self.db.connect() as conn:
            # Regenerating a line invalidates its old candidates and selection.
            conn.execute("DELETE FROM clips WHERE script_line_id = ?", (line.id,))
            conn.execute("UPDATE script_lines SET selected_clip_id = ? WHERE id = ?", ("", line.id))

        created_clip_ids: List[str] = []
        selected_clip_id = ""
        for variant in range(1, controls.variants + 1):
            clip_id = str(uuid.uuid4())
            output_path = line_dir / f"v{variant}.wav"
            variant_controls = GenerationControls.from_dict(controls.to_api())
            if variant_controls.seed is not None:
                # A fixed seed still produces distinct candidates across variants.
                variant_controls.seed += variant - 1
            if job_id:
                self.jobs.update(
                    job_id,
                    progress=completed_before_line + len(created_clip_ids),
                    clip_ids=(prior_clip_ids or []) + created_clip_ids,
                    errors=errors or [],
                    message=f"Generating line {line.line_index}, variant {variant}/{controls.variants}",
                )
            engine = self.adapter.generate(line.text, voice, variant_controls, output_path, variant)
            clip = GeneratedClip(
                id=clip_id,
                project_id=line.project_id,
                script_line_id=line.id,
                variant_index=variant,
                wav_path=str(output_path),
                duration_ms=duration_ms(output_path),
                sample_rate=48_000,
                lufs=estimate_lufs(output_path),
                settings_snapshot={
                    "engine": engine,
                    "controls": variant_controls.to_api(),
                    "voiceId": voice.id,
                    "text": line.text,
                },
                created_at=now_iso(),
            )
            self.db.execute(
                """
                INSERT INTO clips (
                  id, project_id, script_line_id, variant_index, wav_path,
                  duration_ms, sample_rate, lufs, settings_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clip.id,
                    clip.project_id,
                    clip.script_line_id,
                    clip.variant_index,
                    clip.wav_path,
                    clip.duration_ms,
                    clip.sample_rate,
                    clip.lufs,
                    json.dumps(clip.settings_snapshot, ensure_ascii=False),
                    clip.created_at,
                ),
            )
            if not selected_clip_id:
                selected_clip_id = clip_id
            created_clip_ids.append(clip_id)
            if job_id:
                self.jobs.update(
                    job_id,
                    progress=completed_before_line + len(created_clip_ids),
                    clip_ids=(prior_clip_ids or []) + created_clip_ids,
                    errors=errors or [],
                    message=f"Generated line {line.line_index}, variant {variant}/{controls.variants}",
                )

        self.db.execute(
            "UPDATE script_lines SET selected_clip_id = ? WHERE id = ?",
            (selected_clip_id, line.id),
        )
        return created_clip_ids


def _first_voice_id(db: Database) -> str:
    """Return the newest voice id for default script assignment."""

    row = db.query_one("SELECT id FROM voices ORDER BY created_at DESC LIMIT 1")
    return row["id"] if row else ""


def _voice_row_to_dataclass(row: Dict[str, Any]) -> VoiceProfile:
    """Convert a database voice row to the adapter-facing dataclass."""

    return VoiceProfile(
        id=row["id"],
        name=row["name"],
        reference_audio_path=row["reference_audio_path"],
        prompt_audio_path=row["prompt_audio_path"],
        reference_text=row["reference_text"],
        language=row["language"],
        consent_note=row["consent_note"],
        model_prompt_path=row["model_prompt_path"],
        created_at=row["created_at"],
    )


def _line_row_to_dataclass(row: Dict[str, Any]) -> ScriptLine:
    """Convert a database script row to the generation dataclass."""

    return ScriptLine(
        id=row["id"],
        project_id=row["project_id"],
        line_index=row["line_index"],
        text=row["text"],
        voice_id=row["voice_id"],
        controls=GenerationControls.from_dict(json_loads(row["controls_json"])),
        selected_clip_id=row["selected_clip_id"],
    )


def _voice_row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a voice row to the camelCase API payload."""

    return {
        "id": row["id"],
        "name": row["name"],
        "referenceAudioPath": row["reference_audio_path"],
        "promptAudioPath": row["prompt_audio_path"],
        "referenceText": row["reference_text"],
        "language": row["language"],
        "consentNote": row["consent_note"],
        "modelPromptPath": row["model_prompt_path"],
        "createdAt": row["created_at"],
    }


def _project_row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a project row to the camelCase API payload."""

    return {
        "id": row["id"],
        "name": row["name"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _line_row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a script line row to the frontend shape."""

    controls = GenerationControls.from_dict(json_loads(row["controls_json"]))
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "lineIndex": row["line_index"],
        "text": row["text"],
        "voiceId": row["voice_id"],
        "controls": controls.to_api(),
        "selectedClipId": row["selected_clip_id"],
        "clips": [],
    }


def _clip_row_to_api(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a generated clip row to the frontend shape."""

    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "scriptLineId": row["script_line_id"],
        "variantIndex": row["variant_index"],
        "wavPath": row["wav_path"],
        "audioUrl": f"/clips/{row['id']}/audio",
        "durationMs": row["duration_ms"],
        "sampleRate": row["sample_rate"],
        "lufs": row["lufs"],
        "settingsSnapshot": json_loads(row["settings_json"]),
        "createdAt": row["created_at"],
    }


def _preferred_clip(line: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the selected clip for export, falling back to the first candidate."""

    clips = line.get("clips", [])
    if not clips:
        return None
    selected_id = line.get("selectedClipId")
    for clip in clips:
        if clip["id"] == selected_id:
            return clip
    return clips[0]


def _unique_dir(path: Path) -> Path:
    """Return a non-existing directory path by adding a numeric suffix if needed."""

    if not path.exists():
        return path
    for index in range(2, 1_000):
        candidate = path.with_name(f"{path.name}_{index}")
        if not candidate.exists():
            return candidate
    return path.with_name(f"{path.name}_{uuid.uuid4().hex[:8]}")
