"""Script parsing tests for editor paste and export filename behavior."""

import unittest

from backend.app.script import safe_filename, split_script


class ScriptTests(unittest.TestCase):
    """Tests for text splitting and filesystem-safe naming."""

    def test_split_script_keeps_lines_and_punctuation_chunks(self):
        """Manual newlines remain authoritative while long sentences are chunked."""

        text = "第一句。\n第二句很短。\n这是一个比较长的句子，需要按照中文标点切分。这里是第二段内容！最后还有一句？"

        lines = split_script(text, max_chars=26)

        self.assertEqual(lines[0], "第一句。")
        self.assertIn("第二句很短。", lines)
        self.assertTrue(all(len(line) <= 26 for line in lines))
        self.assertGreaterEqual(len(lines), 4)

    def test_safe_filename_removes_bad_chars(self):
        """Unsafe filename characters should not reach exported WAV names."""

        name = safe_filename(3, '客户说："今天/必须*补录?"')

        self.assertEqual(name, "003_客户说今天必须补录.wav")

    def test_split_script_hard_wraps_text_without_sentence_punctuation(self):
        """Very long unpunctuated text still gets bounded chunks."""

        lines = split_script("abcdefghijklmnopqrstuvwxyz", max_chars=7)

        self.assertEqual(lines, ["abcdefg", "hijklmn", "opqrstu", "vwxyz"])


if __name__ == "__main__":
    unittest.main()
