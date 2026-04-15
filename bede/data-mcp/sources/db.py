"""SQLite read layer for data-mcp.

Shares the same schema as data-ingest. Tables are created idempotently
so either service can start first.
"""

import logging
import os
import sqlite3

log = logging.getLogger(__name__)

SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "/data/bede.db")

# Same schema as data-ingest/db.py — keep in sync.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE(date, metric, source, recorded_at)
);
CREATE INDEX IF NOT EXISTS idx_health_date_metric ON health_metrics(date, metric);

CREATE TABLE IF NOT EXISTS sleep_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    stage TEXT NOT NULL,
    hours REAL NOT NULL,
    sleep_start TEXT,
    sleep_end TEXT,
    source TEXT,
    UNIQUE(date, stage)
);
CREATE INDEX IF NOT EXISTS idx_sleep_date ON sleep_phases(date);

CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    workout_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_min REAL,
    active_energy_kj REAL,
    avg_heart_rate_bpm REAL,
    max_heart_rate_bpm REAL,
    UNIQUE(date, workout_name, start_time)
);
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);

CREATE TABLE IF NOT EXISTS state_of_mind (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    valence REAL,
    labels TEXT,
    context TEXT,
    UNIQUE(date, recorded_at)
);
CREATE INDEX IF NOT EXISTS idx_som_date ON state_of_mind(date);

CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity REAL,
    unit TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE(date, name, recorded_at)
);
CREATE INDEX IF NOT EXISTS idx_meds_date ON medications(date);

CREATE TABLE IF NOT EXISTS screen_time (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    device TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    identifier TEXT NOT NULL,
    seconds INTEGER NOT NULL,
    UNIQUE(date, device, entry_type, identifier)
);
CREATE INDEX IF NOT EXISTS idx_screentime_date ON screen_time(date);

CREATE TABLE IF NOT EXISTS safari_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    device TEXT NOT NULL,
    visited_at TEXT NOT NULL,
    domain TEXT,
    title TEXT,
    url TEXT,
    UNIQUE(date, device, url, visited_at)
);
CREATE INDEX IF NOT EXISTS idx_safari_date ON safari_history(date);

CREATE TABLE IF NOT EXISTS youtube_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    visited_at TEXT NOT NULL,
    title TEXT,
    url TEXT,
    UNIQUE(date, url, visited_at)
);
CREATE INDEX IF NOT EXISTS idx_youtube_date ON youtube_history(date);

CREATE TABLE IF NOT EXISTS podcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    episode TEXT,
    podcast TEXT,
    duration_seconds INTEGER,
    played_at TEXT NOT NULL,
    UNIQUE(date, episode, played_at)
);
CREATE INDEX IF NOT EXISTS idx_podcasts_date ON podcasts(date);

CREATE TABLE IF NOT EXISTS claude_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL
);
"""

_db: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    """Return a shared read-only SQLite connection."""
    global _db
    if _db is None:
        _db = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA query_only=ON")
    return _db


def init_db() -> None:
    """Ensure schema exists. Safe to call even if data-ingest already created it."""
    db = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(_SCHEMA_SQL)
        db.commit()
        log.info("data-mcp database ready at %s", SQLITE_DB_PATH)
    finally:
        db.close()
