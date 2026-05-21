"""Shared test fixtures for isolated service and audio setup."""

from __future__ import annotations

from pathlib import Path

from backend.app.audio import write_wav_mono
from backend.app.config import StudioPaths
from backend.app.service import VoiceStudioService


def make_paths(root: Path) -> StudioPaths:
    """Build a full StudioPaths object inside a temporary test directory."""

    return StudioPaths(
        workspace_root=root,
        data_dir=root / "data",
        models_dir=root / "models",
        db_path=root / "data" / "studio.sqlite3",
        original_voice_dir=root / "data" / "voices" / "originals",
        prompt_voice_dir=root / "data" / "voices" / "prompts",
        clip_dir=root / "data" / "clips",
        export_dir=root / "data" / "exports",
        temp_dir=root / "data" / "tmp",
    )


def make_service(root: Path) -> VoiceStudioService:
    """Create a service that cannot touch the real project data directory."""

    return VoiceStudioService(make_paths(root))


def write_reference(path: Path, seconds: int = 2) -> Path:
    """Write a simple valid WAV long enough to pass reference validation."""

    write_wav_mono(path, [0.05] * 48_000 * seconds, 48_000, sample_width=2)
    return path


def create_voice(service: VoiceStudioService, root: Path, name: str = "Test Voice") -> dict:
    """Register a reusable test voice with a generated reference WAV."""

    reference = write_reference(root / "reference.wav")
    return service.create_voice(
        name=name,
        source_audio_path=reference,
        original_filename="reference.wav",
        reference_text="这是一段授权参考音频。",
    )
