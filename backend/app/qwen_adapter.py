from __future__ import annotations

import gc
import inspect
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .audio import postprocess_wav, synthesize_placeholder
from .config import StudioPaths
from .types import GenerationControls, VoiceProfile


MODEL_CANDIDATES = (
    "Qwen3-TTS-12Hz-1.7B-Base-8bit",
    "Qwen3-TTS-12Hz-1.7B-Base",
    "Qwen3-TTS-12Hz-0.6B-Base-8bit",
    "Qwen3-TTS-12Hz-0.6B-Base",
)


@dataclass
class AdapterStatus:
    backend: str
    available: bool
    model_path: str
    message: str
    candidate_models: list[str]

    def to_api(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "modelPath": self.model_path,
            "message": self.message,
            "candidateModels": self.candidate_models,
        }


class Qwen3TTSAdapter:
    """Best-effort adapter for local Qwen3-TTS on Apple Silicon.

    The real path uses `mlx_audio.tts.generate.generate_audio`, matching the
    community Apple Silicon implementation. When dependencies or weights are
    missing, the adapter returns deterministic preview WAVs so the Studio
    workflow remains testable before model setup.
    """

    def __init__(self, paths: StudioPaths):
        self.paths = paths
        self._model: Optional[Any] = None
        self._model_path: Optional[Path] = None
        self._load_error = ""
        self._lock = threading.Lock()

    def status(self) -> AdapterStatus:
        model_path = self._resolve_model_path()
        candidates = [str(path) for path in self._candidate_model_paths()]
        if not model_path:
            return AdapterStatus(
                backend="preview",
                available=False,
                model_path="",
                message="No Qwen3-TTS Base model found in models/. Preview WAV generation is active.",
                candidate_models=candidates,
            )
        try:
            self._import_mlx()
        except ImportError as exc:
            return AdapterStatus(
                backend="preview",
                available=False,
                model_path=str(model_path),
                message=f"MLX audio dependency is not installed: {exc}",
                candidate_models=candidates,
            )
        except Exception as exc:  # noqa: BLE001 - status must not crash the API.
            return AdapterStatus(
                backend="preview",
                available=False,
                model_path=str(model_path),
                message=f"MLX audio is installed, but this process cannot use it yet: {exc}",
                candidate_models=candidates,
            )
        return AdapterStatus(
            backend="mlx-audio",
            available=True,
            model_path=str(model_path),
            message="Qwen3-TTS model and MLX audio dependency were detected.",
            candidate_models=candidates,
        )

    def generate(
        self,
        text: str,
        voice: VoiceProfile,
        controls: GenerationControls,
        output_path: Path,
        variant_index: int,
    ) -> str:
        controls = controls.validated()
        with self._lock:
            status = self.status()
            if status.available:
                try:
                    return self._generate_with_mlx(text, voice, controls, output_path)
                except Exception as exc:  # noqa: BLE001 - we must fail soft for editor workflow.
                    self._load_error = str(exc)

            seed_source = voice.id + voice.name + str(variant_index)
            voice_seed = sum(ord(char) for char in seed_source)
            synthesize_placeholder(text, output_path, controls, voice_seed=voice_seed)
            return "preview"

    def _generate_with_mlx(
        self,
        text: str,
        voice: VoiceProfile,
        controls: GenerationControls,
        output_path: Path,
    ) -> str:
        _, generate_audio = self._import_mlx()
        model_path = self._load_model_with_fallback()

        with tempfile.TemporaryDirectory(prefix="voice_patch_") as temp_dir:
            kwargs: Dict[str, Any] = {
                "model": self._model,
                "text": text,
                "ref_audio": voice.prompt_audio_path,
                "ref_text": voice.reference_text or ".",
                "output_path": temp_dir,
            }
            signature = inspect.signature(generate_audio)
            if "speed" in signature.parameters:
                kwargs["speed"] = controls.speed
            if controls.emotion_hint and "instruct" in signature.parameters:
                kwargs["instruct"] = controls.emotion_hint
            generate_audio(**kwargs)
            source = Path(temp_dir) / "audio_000.wav"
            if not source.exists():
                candidates = list(Path(temp_dir).glob("*.wav"))
                if not candidates:
                    raise RuntimeError("Qwen3-TTS did not create a WAV file.")
                source = candidates[0]
            postprocess_wav(source, output_path, controls)
        return "mlx-audio"

    def _resolve_model_path(self) -> Optional[Path]:
        candidates = self._candidate_model_paths()
        return candidates[0] if candidates else None

    def _candidate_model_paths(self) -> list[Path]:
        candidates: list[Path] = []
        for folder in MODEL_CANDIDATES:
            candidate = self.paths.models_dir / folder
            resolved = _resolve_snapshot(candidate)
            if resolved:
                candidates.append(resolved)
        return candidates

    def _load_model_with_fallback(self) -> Path:
        load_model, _ = self._import_mlx()
        candidates = self._candidate_model_paths()
        if not candidates:
            raise RuntimeError("No Qwen3-TTS model is available.")
        if self._model is not None and self._model_path in candidates:
            assert self._model_path is not None
            return self._model_path

        errors: list[str] = []
        for model_path in candidates:
            try:
                gc.collect()
                self._model = load_model(str(model_path))
                self._model_path = model_path
                self._load_error = ""
                return model_path
            except Exception as exc:  # noqa: BLE001 - fallback is the product behavior.
                errors.append(f"{model_path.name}: {exc}")
                self._model = None
                self._model_path = None
        self._load_error = " | ".join(errors)
        raise RuntimeError(self._load_error)

    @staticmethod
    def _import_mlx() -> Any:
        from mlx_audio.tts.generate import generate_audio
        from mlx_audio.tts.utils import load_model

        return load_model, generate_audio


def _resolve_snapshot(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    snapshots = path / "snapshots"
    if snapshots.exists():
        children = [child for child in snapshots.iterdir() if child.is_dir() and not child.name.startswith(".")]
        if children:
            return children[0]
    return path


def copy_export_clip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
