"""Tests for SQLite schema initialization and basic operations."""

import sqlite3
import tempfile
import os

import pytest

# Point to a temp database before importing db module
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SQLITE_DB_PATH"] = _tmp.name

from db import get_db, init_db, SCHEMA_VERSION


@pytest.fixture(autouse=True)
def _fresh_db():
    """Re-initialize database before each test."""
    # Remove and recreate
    if os.path.exists(_tmp.name):
        os.unlink(_tmp.name)
    # Also remove WAL files
    for ext in ("-wal", "-shm"):
        p = _tmp.name + ext
        if os.path.exists(p):
            os.unlink(p)
    init_db()
    yield


def test_schema_version():
    db = get_db()
    row = db.execute("SELECT version FROM schema_version").fetchone()
    assert row["version"] == SCHEMA_VERSION
    db.close()


def test_wal_mode():
    db = get_db()
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    db.close()


def test_all_tables_exist():
    expected_tables = {
        "schema_version",
        "health_metrics",
        "sleep_phases",
        "workouts",
        "state_of_mind",
        "medications",
        "screen_time",
        "safari_history",
        "youtube_history",
        "podcasts",
        "claude_sessions",
    }
    db = get_db()
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = {r["name"] for r in rows}
    assert expected_tables.issubset(tables)
    db.close()


def test_health_metrics_insert_and_query():
    db = get_db()
    db.execute(
        "INSERT INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
        ("2026-04-14", "step_count", 8423, "iPhone", "2026-04-14T06:00:00Z"),
    )
    db.commit()
    row = db.execute("SELECT * FROM health_metrics WHERE date = '2026-04-14'").fetchone()
    assert row["metric"] == "step_count"
    assert row["value"] == 8423
    assert row["source"] == "iPhone"
    db.close()


def test_health_metrics_idempotent():
    db = get_db()
    for _ in range(3):
        db.execute(
            "INSERT OR IGNORE INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-14", "step_count", 8423, "iPhone", "2026-04-14T06:00:00Z"),
        )
        db.commit()
    count = db.execute("SELECT COUNT(*) FROM health_metrics").fetchone()[0]
    assert count == 1
    db.close()


def test_health_metrics_multi_source():
    """Different sources for the same metric should both be stored."""
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
        ("2026-04-14", "step_count", 5000, "iPhone", "2026-04-14T06:00:00Z"),
    )
    db.execute(
        "INSERT OR IGNORE INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
        ("2026-04-14", "step_count", 3423, "Apple Watch", "2026-04-14T06:00:00Z"),
    )
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM health_metrics WHERE date = '2026-04-14' AND metric = 'step_count'").fetchone()[0]
    assert count == 2
    db.close()


def test_sleep_phases_insert():
    db = get_db()
    db.execute(
        "INSERT INTO sleep_phases (date, stage, hours, sleep_start, sleep_end, source) VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-04-14", "deep", 1.5, "2026-04-13T22:30:00Z", "2026-04-14T06:30:00Z", "Apple Watch"),
    )
    db.commit()
    row = db.execute("SELECT * FROM sleep_phases WHERE date = '2026-04-14'").fetchone()
    assert row["stage"] == "deep"
    assert row["hours"] == 1.5
    db.close()


def test_workouts_insert():
    db = get_db()
    db.execute(
        "INSERT INTO workouts (date, workout_name, start_time, end_time, duration_min, active_energy_kj, avg_heart_rate_bpm, max_heart_rate_bpm) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-04-14", "Running", "2026-04-14T06:30:00Z", "2026-04-14T07:00:00Z", 30.0, 1200.5, 155, 178),
    )
    db.commit()
    row = db.execute("SELECT * FROM workouts WHERE date = '2026-04-14'").fetchone()
    assert row["workout_name"] == "Running"
    assert row["duration_min"] == 30.0
    db.close()


def test_screen_time_insert():
    db = get_db()
    db.execute(
        "INSERT INTO screen_time (date, device, entry_type, identifier, seconds) VALUES (?, ?, ?, ?, ?)",
        ("2026-04-14", "mac", "app", "com.apple.Safari", 3600),
    )
    db.commit()
    row = db.execute("SELECT * FROM screen_time WHERE date = '2026-04-14'").fetchone()
    assert row["identifier"] == "com.apple.Safari"
    assert row["seconds"] == 3600
    db.close()


def test_claude_sessions_insert_and_replace():
    db = get_db()
    db.execute(
        "INSERT INTO claude_sessions (date, content) VALUES (?, ?)",
        ("2026-04-14", "## Session 1\nDid some work."),
    )
    db.commit()
    # Replace with updated content
    db.execute(
        "INSERT OR REPLACE INTO claude_sessions (date, content) VALUES (?, ?)",
        ("2026-04-14", "## Session 1\nDid some work.\n## Session 2\nMore work."),
    )
    db.commit()
    row = db.execute("SELECT * FROM claude_sessions WHERE date = '2026-04-14'").fetchone()
    assert "Session 2" in row["content"]
    count = db.execute("SELECT COUNT(*) FROM claude_sessions").fetchone()[0]
    assert count == 1
    db.close()


def test_readonly_connection():
    db = get_db(readonly=True)
    # Reads should work
    db.execute("SELECT COUNT(*) FROM health_metrics").fetchone()
    # Writes should fail
    with pytest.raises(sqlite3.OperationalError):
        db.execute(
            "INSERT INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-14", "step_count", 100, "test", "2026-04-14T00:00:00Z"),
        )
    db.close()
