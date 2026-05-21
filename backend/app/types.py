"""Dataclasses that define backend controls and core domain records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


def clamp(value: float, low: float, high: float) -> float:
    """Clamp numeric user input to an inclusive range."""

    return min(high, max(low, value))


@dataclass
class GenerationControls:
    """User-facing generation controls with validation and API conversion."""

    speed: float = 1.0
    pitch_semitones: float = 0.0
    gain_db: float = 0.0
    emotion_hint: str = ""
    pause_ms: int = 0
    seed: Optional[int] = None
    variants: int = 1

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "GenerationControls":
        """Accept both frontend camelCase keys and backend snake_case keys."""

        payload = payload or {}
        controls = cls(
            speed=float(payload.get("speed", 1.0)),
            pitch_semitones=float(payload.get("pitchSemitones", payload.get("pitch_semitones", 0.0))),
            gain_db=float(payload.get("gainDb", payload.get("gain_db", 0.0))),
            emotion_hint=str(payload.get("emotionHint", payload.get("emotion_hint", ""))).strip(),
            pause_ms=int(payload.get("pauseMs", payload.get("pause_ms", 0))),
            seed=payload.get("seed"),
            variants=int(payload.get("variants", 1)),
        )
        return controls.validated()

    def validated(self) -> "GenerationControls":
        """Return a safe copy with all values clamped to product limits."""

        seed = None if self.seed in ("", None) else int(self.seed)
        return GenerationControls(
            speed=round(clamp(float(self.speed), 0.55, 1.75), 3),
            pitch_semitones=round(clamp(float(self.pitch_semitones), -6.0, 6.0), 2),
            gain_db=round(clamp(float(self.gain_db), -12.0, 6.0), 2),
            emotion_hint=self.emotion_hint[:160],
            pause_ms=int(clamp(int(self.pause_ms), 0, 2000)),
            seed=seed,
            variants=int(clamp(int(self.variants), 1, 5)),
        )

    def to_json(self) -> str:
        """Serialize controls in the frontend/API field naming convention."""

        return json.dumps(self.to_api(), ensure_ascii=False)

    def to_api(self) -> Dict[str, Any]:
        """Return controls as the camelCase object consumed by React."""

        data = asdict(self.validated())
        return {
            "speed": data["speed"],
            "pitchSemitones": data["pitch_semitones"],
            "gainDb": data["gain_db"],
            "emotionHint": data["emotion_hint"],
            "pauseMs": data["pause_ms"],
            "seed": data["seed"],
            "variants": data["variants"],
        }


@dataclass
class VoiceProfile:
    """Stored voice reference and prompt-audio metadata."""

    id: str
    name: str
    reference_audio_path: str
    prompt_audio_path: str
    reference_text: str
    language: str
    consent_note: str
    model_prompt_path: str = ""
    created_at: str = ""


@dataclass
class ScriptLine:
    """One generated-audio unit from the pasted script."""

    id: str
    project_id: str
    line_index: int
    text: str
    voice_id: str
    controls: GenerationControls = field(default_factory=GenerationControls)
    selected_clip_id: str = ""


@dataclass
class GeneratedClip:
    """One generated WAV candidate for a script line."""

    id: str
    project_id: str
    script_line_id: str
    variant_index: int
    wav_path: str
    duration_ms: int
    sample_rate: int
    lufs: float
    settings_snapshot: Dict[str, Any]
    created_at: str = ""
