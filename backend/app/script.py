"""Script splitting and export filename helpers."""

from __future__ import annotations

import re
from typing import Iterable, List


BAD_FILENAME_CHARS = re.compile(r'[\\/:：*?"“”<>|\r\n\t]+')
ENDING_PUNCTUATION = re.compile(r"(?<=[。！？!?；;])")


def split_script(text: str, max_chars: int = 84) -> List[str]:
    """Split pasted editor copy into short TTS lines.

    New lines stay authoritative. Long lines are split at Chinese and common
    sentence punctuation so each generated clip remains easy to replace.
    """

    result: List[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) <= max_chars:
            result.append(line)
            continue

        buffer = ""
        for part in ENDING_PUNCTUATION.split(line):
            part = part.strip()
            if not part:
                continue
            if len(buffer) + len(part) <= max_chars:
                buffer += part
                continue
            if buffer:
                result.append(buffer)
            if len(part) <= max_chars:
                buffer = part
            else:
                result.extend(_hard_wrap(part, max_chars))
                buffer = ""
        if buffer:
            result.append(buffer)
    return result


def _hard_wrap(text: str, max_chars: int) -> Iterable[str]:
    """Fallback splitter for long text without sentence punctuation."""

    for start in range(0, len(text), max_chars):
        chunk = text[start : start + max_chars].strip()
        if chunk:
            yield chunk


def safe_filename(index: int, text: str, extension: str = ".wav", max_text_chars: int = 24) -> str:
    """Build a filesystem-safe exported WAV name from line index and text."""

    cleaned = BAD_FILENAME_CHARS.sub("", text).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)[:max_text_chars].strip("._ ")
    if not cleaned:
        cleaned = "audio"
    return f"{index:03d}_{cleaned}{extension}"
