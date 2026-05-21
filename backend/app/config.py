from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StudioPaths:
    workspace_root: Path
    data_dir: Path
    models_dir: Path
    db_path: Path
    original_voice_dir: Path
    prompt_voice_dir: Path
    clip_dir: Path
    export_dir: Path
    temp_dir: Path

    @classmethod
    def from_env(cls) -> "StudioPaths":
        backend_root = Path(__file__).resolve().parents[1]
        workspace_root = backend_root.parent
        data_dir = Path(os.environ.get("VOICE_STUDIO_DATA_DIR", workspace_root / "data"))
        models_dir = Path(os.environ.get("VOICE_STUDIO_MODELS_DIR", workspace_root / "models"))
        return cls(
            workspace_root=workspace_root,
            data_dir=data_dir,
            models_dir=models_dir,
            db_path=Path(os.environ.get("VOICE_STUDIO_DB", data_dir / "studio.sqlite3")),
            original_voice_dir=data_dir / "voices" / "originals",
            prompt_voice_dir=data_dir / "voices" / "prompts",
            clip_dir=data_dir / "clips",
            export_dir=data_dir / "exports",
            temp_dir=data_dir / "tmp",
        )

    def ensure(self) -> None:
        for path in (
            self.data_dir,
            self.models_dir,
            self.original_voice_dir,
            self.prompt_voice_dir,
            self.clip_dir,
            self.export_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


DEFAULT_LANGUAGE = "Chinese"
PROMPT_SAMPLE_RATE = 24_000
EXPORT_SAMPLE_RATE = 48_000
DEFAULT_REFERENCE_DURATION_MS = 10_000
