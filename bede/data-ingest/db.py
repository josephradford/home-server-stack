"""SQLite database layer — shared schema for data-ingest and data-mcp."""

import logging
import os
import sqlite3

log = logging.getLogger(__name__)

SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "/data/bede.db")

SCHEMA_VERSION = 3

SCHEMA_SQL = """
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
    date TEXT NOT NULL,
    project TEXT NOT NULL,
    start_time TEXT,                   -- local datetime YYYY-MM-DD HH:MM
    end_time TEXT,                     -- local datetime YYYY-MM-DD HH:MM
    duration_min INTEGER,
    turns INTEGER,
    summary TEXT,
    UNIQUE(date, project, start_time)
);
CREATE INDEX IF NOT EXISTS idx_claude_date ON claude_sessions(date);

CREATE TABLE IF NOT EXISTS bede_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    project TEXT NOT NULL,
    start_time TEXT,                   -- local datetime YYYY-MM-DD HH:MM
    end_time TEXT,                     -- local datetime YYYY-MM-DD HH:MM
    duration_min INTEGER,
    turns INTEGER,
    summary TEXT,
    UNIQUE(date, project, start_time)
);
CREATE INDEX IF NOT EXISTS idx_bede_date ON bede_sessions(date);
"""


def get_db(readonly: bool = False) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and row factory."""
    db = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    if readonly:
        db.execute("PRAGMA query_only=ON")
    return db


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    db = get_db()
    try:
        db.executescript(SCHEMA_SQL)
        # Record schema version
        db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        db.commit()
        log.info("Database initialized at %s (schema v%d)", SQLITE_DB_PATH, SCHEMA_VERSION)
    finally:
        db.close()
