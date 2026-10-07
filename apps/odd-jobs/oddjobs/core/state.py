"""SQLite record of each job's last run."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunRecord:
    job: str
    last_run_at: float
    last_success_at: float | None
    ok: bool
    detail: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    job TEXT PRIMARY KEY,
    last_run_at REAL NOT NULL,
    last_success_at REAL,
    ok INTEGER NOT NULL,
    detail TEXT NOT NULL
)
"""


class State:
    def __init__(self, path: Path):
        self._path = str(path)
        with self._connect() as db:
            db.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # One short-lived connection per call keeps this safe across threads.
        return sqlite3.connect(self._path, timeout=10)

    def record_success(self, job: str, detail: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs (job, last_run_at, last_success_at, ok, detail) VALUES (?, ?, ?, 1, ?) "
                "ON CONFLICT(job) DO UPDATE SET last_run_at=excluded.last_run_at, "
                "last_success_at=excluded.last_success_at, ok=1, detail=excluded.detail",
                (job, now, now, detail),
            )

    def record_failure(self, job: str, error: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._connect() as db:
            db.execute(
                "INSERT INTO runs (job, last_run_at, last_success_at, ok, detail) VALUES (?, ?, NULL, 0, ?) "
                "ON CONFLICT(job) DO UPDATE SET last_run_at=excluded.last_run_at, ok=0, detail=excluded.detail",
                (job, now, error),
            )

    def get(self, job: str) -> RunRecord | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT job, last_run_at, last_success_at, ok, detail FROM runs WHERE job=?", (job,)
            ).fetchone()
        return _record(row) if row else None


def _record(row: tuple) -> RunRecord:
    return RunRecord(job=row[0], last_run_at=row[1], last_success_at=row[2], ok=bool(row[3]), detail=row[4])
