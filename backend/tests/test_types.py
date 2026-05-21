import unittest

from backend.app.types import GenerationControls


class GenerationControlsTests(unittest.TestCase):
    def test_from_dict_accepts_api_and_snake_case_keys(self):
        controls = GenerationControls.from_dict(
            {
                "speed": "1.23456",
                "pitch_semitones": "2.5",
                "gainDb": "-3",
                "emotion_hint": "温柔一些",
                "pauseMs": "250",
                "seed": "123",
                "variants": "3",
            }
        )

        self.assertEqual(controls.to_api()["speed"], 1.235)
        self.assertEqual(controls.to_api()["pitchSemitones"], 2.5)
        self.assertEqual(controls.to_api()["gainDb"], -3.0)
        self.assertEqual(controls.to_api()["emotionHint"], "温柔一些")
        self.assertEqual(controls.to_api()["pauseMs"], 250)
        self.assertEqual(controls.to_api()["seed"], 123)
        self.assertEqual(controls.to_api()["variants"], 3)

    def test_validation_clamps_user_controls(self):
        controls = GenerationControls.from_dict(
            {
                "speed": 99,
                "pitchSemitones": -99,
                "gainDb": 99,
                "emotionHint": "x" * 200,
                "pauseMs": 9999,
                "seed": "",
                "variants": 99,
            }
        )

        self.assertEqual(controls.speed, 1.75)
        self.assertEqual(controls.pitch_semitones, -6.0)
        self.assertEqual(controls.gain_db, 6.0)
        self.assertEqual(len(controls.emotion_hint), 160)
        self.assertEqual(controls.pause_ms, 2000)
        self.assertIsNone(controls.seed)
        self.assertEqual(controls.variants, 5)


if __name__ == "__main__":
    unittest.main()
