"""SQLite schema and small query helpers for the local studio database."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS voices (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  reference_audio_path TEXT NOT NULL,
  prompt_audio_path TEXT NOT NULL,
  reference_text TEXT NOT NULL,
  language TEXT NOT NULL,
  consent_note TEXT NOT NULL DEFAULT '',
  model_prompt_path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS script_lines (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  line_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  voice_id TEXT NOT NULL DEFAULT '',
  controls_json TEXT NOT NULL,
  selected_clip_id TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clips (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  script_line_id TEXT NOT NULL,
  variant_index INTEGER NOT NULL,
  wav_path TEXT NOT NULL,
  duration_ms INTEGER NOT NULL,
  sample_rate INTEGER NOT NULL,
  lufs REAL NOT NULL,
  settings_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(script_line_id) REFERENCES script_lines(id) ON DELETE CASCADE
);
"""


class Database:
    """Thin wrapper that keeps SQLite setup and row conversion in one place."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a short-lived connection with row dictionaries and FK checks."""

        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        """Create all tables if this is a fresh data directory."""

        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        """Execute a write statement in its own transaction."""

        with self.connect() as conn:
            conn.execute(sql, tuple(params))

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        """Return one row as a dict, or None when no row matched."""

        with self.connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        """Return all matching rows as plain dictionaries."""

        with self.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]


def json_dumps(payload: Dict[str, Any]) -> str:
    """Serialize small settings payloads consistently for SQLite storage."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def json_loads(payload: str) -> Dict[str, Any]:
    """Deserialize settings payloads, treating blank strings as empty objects."""

    return json.loads(payload or "{}")
