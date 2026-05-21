from __future__ import annotations

import math
import os
import random
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from .config import EXPORT_SAMPLE_RATE, PROMPT_SAMPLE_RATE
from .types import GenerationControls


class AudioError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def read_wav_mono(path: Path) -> Tuple[List[float], int]:
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except wave.Error as exc:
        raise AudioError(f"Unsupported WAV file: {path}") from exc

    if channels <= 0:
        raise AudioError(f"WAV has no channels: {path}")

    frame_width = channels * sample_width
    samples: List[float] = []
    for offset in range(0, len(frames), frame_width):
        values = []
        for channel in range(channels):
            start = offset + channel * sample_width
            chunk = frames[start : start + sample_width]
            values.append(_decode_sample(chunk, sample_width))
        samples.append(sum(values) / len(values))
    return samples, sample_rate


def write_wav_mono(path: Path, samples: Sequence[float], sample_rate: int, sample_width: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(_encode_sample(sample, sample_width) for sample in samples))


def convert_reference_audio(
    source_path: Path,
    target_path: Path,
    trim_start_ms: int = 0,
    trim_duration_ms: int = 10_000,
) -> None:
    source_path = Path(source_path)
    target_path = Path(target_path)
    working_source = source_path
    temp_name = None

    if source_path.suffix.lower() != ".wav":
        if not ffmpeg_available():
            raise AudioError("MP3/M4A import requires ffmpeg. Install ffmpeg, or import a WAV file first.")
        fd, temp_name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        Path(temp_name).unlink(missing_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source_path),
            "-ar",
            str(PROMPT_SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            temp_name,
        ]
        try:
            subprocess.run(cmd, check=True)
            working_source = Path(temp_name)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise AudioError("Could not convert reference audio with ffmpeg.") from exc

    samples, sample_rate = read_wav_mono(working_source)
    if temp_name:
        Path(temp_name).unlink(missing_ok=True)

    start = max(0, int(sample_rate * trim_start_ms / 1000))
    end = start + max(1, int(sample_rate * trim_duration_ms / 1000))
    trimmed = samples[start:end]
    if len(trimmed) < sample_rate:
        raise AudioError("Reference audio should contain at least one second of clean speech.")

    resampled = linear_resample(trimmed, sample_rate, PROMPT_SAMPLE_RATE)
    normalized = normalize_peak(resampled, ceiling=0.86)
    write_wav_mono(target_path, normalized, PROMPT_SAMPLE_RATE, sample_width=2)


def postprocess_wav(source_path: Path, target_path: Path, controls: GenerationControls) -> None:
    controls = controls.validated()
    if ffmpeg_available():
        try:
            _postprocess_with_ffmpeg(source_path, target_path, controls)
            return
        except AudioError:
            pass

    samples, sample_rate = read_wav_mono(source_path)
    samples = linear_resample(samples, sample_rate, EXPORT_SAMPLE_RATE)
    samples = apply_gain(samples, controls.gain_db)
    if controls.pause_ms:
        samples = list(samples) + [0.0] * int(EXPORT_SAMPLE_RATE * controls.pause_ms / 1000)
    samples = normalize_peak(samples, ceiling=0.98)
    write_wav_mono(target_path, samples, EXPORT_SAMPLE_RATE, sample_width=3)


def synthesize_placeholder(
    text: str,
    target_path: Path,
    controls: GenerationControls,
    voice_seed: int,
) -> None:
    controls = controls.validated()
    seed = controls.seed if controls.seed is not None else voice_seed
    rng = random.Random(seed + len(text) * 31)
    base_frequency = 138.0 + (seed % 35) * 3.5
    pitch_factor = 2 ** (controls.pitch_semitones / 12.0)
    punctuation_pauses = sum(1 for char in text if char in "，,。.!！？?；;")
    estimated_seconds = max(0.85, min(18.0, (len(text) * 0.155 + punctuation_pauses * 0.12) / controls.speed))
    total_samples = int(EXPORT_SAMPLE_RATE * estimated_seconds)
    samples: List[float] = []

    emotion_boost = 1.0
    hint = controls.emotion_hint.lower()
    if any(word in hint for word in ("angry", "excited", "快", "激动", "愤怒")):
        emotion_boost = 1.22
    elif any(word in hint for word in ("sad", "slow", "低落", "难过", "慢")):
        emotion_boost = 0.82

    for i in range(total_samples):
        t = i / EXPORT_SAMPLE_RATE
        progress = i / max(1, total_samples - 1)
        envelope = min(1.0, i / (EXPORT_SAMPLE_RATE * 0.035), (total_samples - i) / (EXPORT_SAMPLE_RATE * 0.07))
        vibrato = 1.0 + 0.018 * math.sin(2 * math.pi * (4.0 + rng.random() * 0.5) * t)
        phrase = 1.0 + 0.08 * math.sin(2 * math.pi * (0.35 + len(text) % 7 * 0.03) * t)
        freq = base_frequency * pitch_factor * vibrato * phrase * emotion_boost
        carrier = math.sin(2 * math.pi * freq * t)
        harmonic = 0.36 * math.sin(2 * math.pi * freq * 2.01 * t + 0.4)
        breath = 0.018 * math.sin(2 * math.pi * (900 + seed % 200) * t) * (1.0 - progress)
        samples.append((carrier + harmonic + breath) * 0.18 * envelope)

    if controls.pause_ms:
        samples.extend([0.0] * int(EXPORT_SAMPLE_RATE * controls.pause_ms / 1000))
    samples = apply_gain(samples, controls.gain_db)
    samples = normalize_peak(samples, ceiling=0.78)
    write_wav_mono(target_path, samples, EXPORT_SAMPLE_RATE, sample_width=3)


def duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        return int(wav.getnframes() / wav.getframerate() * 1000)


def estimate_lufs(path: Path) -> float:
    samples, _ = read_wav_mono(path)
    if not samples:
        return -120.0
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    if rms <= 0:
        return -120.0
    return round(20 * math.log10(rms), 2)


def linear_resample(samples: Sequence[float], source_rate: int, target_rate: int) -> List[float]:
    if source_rate == target_rate:
        return list(samples)
    if not samples:
        return []
    target_len = max(1, int(len(samples) * target_rate / source_rate))
    ratio = (len(samples) - 1) / max(1, target_len - 1)
    output: List[float] = []
    for i in range(target_len):
        pos = i * ratio
        left = int(pos)
        right = min(left + 1, len(samples) - 1)
        frac = pos - left
        output.append(samples[left] * (1.0 - frac) + samples[right] * frac)
    return output


def apply_gain(samples: Iterable[float], gain_db: float) -> List[float]:
    factor = 10 ** (gain_db / 20.0)
    return [sample * factor for sample in samples]


def normalize_peak(samples: Sequence[float], ceiling: float = 0.98) -> List[float]:
    peak = max((abs(sample) for sample in samples), default=0.0)
    if peak <= ceiling or peak == 0:
        return list(samples)
    factor = ceiling / peak
    return [sample * factor for sample in samples]


def _postprocess_with_ffmpeg(source_path: Path, target_path: Path, controls: GenerationControls) -> None:
    filters: List[str] = []
    pitch_factor = 2 ** (controls.pitch_semitones / 12.0)
    if abs(pitch_factor - 1.0) > 0.005:
        filters.extend(
            [
                f"asetrate={EXPORT_SAMPLE_RATE}*{pitch_factor:.6f}",
                f"aresample={EXPORT_SAMPLE_RATE}",
                f"atempo={1 / pitch_factor:.6f}",
            ]
        )
    if abs(controls.speed - 1.0) > 0.005:
        filters.append(f"atempo={controls.speed:.6f}")
    if abs(controls.gain_db) > 0.005:
        filters.append(f"volume={controls.gain_db:.3f}dB")
    if controls.pause_ms:
        filters.append(f"apad=pad_dur={controls.pause_ms / 1000:.3f}")

    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source_path),
    ]
    if filters:
        command.extend(["-af", ",".join(filters)])
    command.extend(["-ar", str(EXPORT_SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s24le", str(target_path)])
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise AudioError("ffmpeg postprocess failed") from exc


def _decode_sample(chunk: bytes, sample_width: int) -> float:
    if sample_width == 1:
        return (chunk[0] - 128) / 128.0
    if sample_width == 2:
        return int.from_bytes(chunk, "little", signed=True) / 32768.0
    if sample_width == 3:
        padded = chunk + (b"\xff" if chunk[2] & 0x80 else b"\x00")
        return int.from_bytes(padded, "little", signed=True) / 8388608.0
    if sample_width == 4:
        return int.from_bytes(chunk, "little", signed=True) / 2147483648.0
    raise AudioError(f"Unsupported sample width: {sample_width}")


def _encode_sample(sample: float, sample_width: int) -> bytes:
    sample = max(-1.0, min(1.0, sample))
    if sample_width == 2:
        value = int(sample * 32767)
        return value.to_bytes(2, "little", signed=True)
    if sample_width == 3:
        value = int(sample * 8388607)
        return value.to_bytes(4, "little", signed=True)[:3]
    if sample_width == 4:
        value = int(sample * 2147483647)
        return value.to_bytes(4, "little", signed=True)
    raise AudioError(f"Unsupported output sample width: {sample_width}")
