"""Audio helper tests for WAV format guarantees and validation failures."""

import tempfile
import unittest
import wave
from pathlib import Path

from backend.app.audio import AudioError, convert_reference_audio, duration_ms, synthesize_placeholder, write_wav_mono
from backend.app.types import GenerationControls


class AudioTests(unittest.TestCase):
    """Tests for audio utilities that do not need real model inference."""

    def test_placeholder_writes_48k_24bit_wav(self):
        """Preview synthesis should emit editor-ready 48 kHz 24-bit mono WAV."""

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "clip.wav"
            synthesize_placeholder(
                "这是一个测试片段。",
                target,
                GenerationControls(speed=1.1, pitch_semitones=1, gain_db=-2, pause_ms=120),
                voice_seed=42,
            )

            with wave.open(str(target), "rb") as wav:
                self.assertEqual(wav.getframerate(), 48_000)
                self.assertEqual(wav.getsampwidth(), 3)
                self.assertEqual(wav.getnchannels(), 1)
            self.assertGreater(duration_ms(target), 500)

    def test_convert_reference_rejects_short_audio(self):
        """Reference imports shorter than one second should be rejected."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "short.wav"
            target = root / "prompt.wav"
            write_wav_mono(source, [0.05] * 12_000, 48_000, sample_width=2)

            with self.assertRaises(AudioError):
                convert_reference_audio(source, target)


if __name__ == "__main__":
    unittest.main()
