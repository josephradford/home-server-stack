"""Parse vault CSV-in-JSON payloads into SQLite rows.

Expected payload:
    {
      "date": "2026-04-14",
      "files": {
        "screentime.csv": "identifier,type,seconds\\n...",
        "iphone-screentime.csv": "...",
        "safari-pages.csv": "visited_at,domain,title,url\\n...",
        "iphone-safari-pages.csv": "...",
        "youtube.csv": "visited_at,title,url\\n...",
        "podcasts.csv": "episode,podcast,duration_seconds,played_at\\n...",
        "claude-sessions.md": "## Session 1\\n..."
      }
    }

CSV column names use the same fallback patterns as the original vault.py:
- Screen time: identifier/app/bundle_id/name, type, seconds/duration, domain
- Safari: visited_at, domain, title, url
- YouTube: visited_at, title, url
- Podcasts: episode/title, podcast/show, duration_seconds/duration, played_at
"""

import csv
import io
import logging
import sqlite3

from db import get_db

log = logging.getLogger(__name__)

# Map filenames to (device, parser_function)
_SCREENTIME_FILES = {
    "screentime.csv": "mac",
    "iphone-screentime.csv": "iphone",
}

_SAFARI_FILES = {
    "safari-pages.csv": "mac",
    "iphone-safari-pages.csv": "iphone",
}


def _parse_csv(content: str) -> list[dict]:
    """Parse CSV string into list of dicts."""
    return list(csv.DictReader(io.StringIO(content)))


def _ingest_screentime(db: sqlite3.Connection, date: str, device: str, content: str) -> int:
    """Parse and insert screen time CSV rows."""
    rows = _parse_csv(content)
    if not rows:
        return 0

    # Delete existing data for this date+device (full daily replacement)
    db.execute("DELETE FROM screen_time WHERE date = ? AND device = ?", (date, device))

    count = 0
    for row in rows:
        identifier = row.get("identifier") or row.get("app") or row.get("bundle_id") or row.get("name", "")
        if not identifier:
            continue

        try:
            seconds = int(float(row.get("seconds", row.get("duration", 0))))
        except (ValueError, TypeError):
            seconds = 0

        if row.get("type") == "web" or "domain" in row:
            entry_type = "web"
            identifier = row.get("domain", identifier)
        else:
            entry_type = "app"

        db.execute(
            "INSERT OR REPLACE INTO screen_time (date, device, entry_type, identifier, seconds) VALUES (?, ?, ?, ?, ?)",
            (date, device, entry_type, identifier, seconds),
        )
        count += 1

    return count


def _ingest_safari(db: sqlite3.Connection, date: str, device: str, content: str) -> int:
    """Parse and insert Safari history CSV rows."""
    rows = _parse_csv(content)
    if not rows:
        return 0

    db.execute("DELETE FROM safari_history WHERE date = ? AND device = ?", (date, device))

    count = 0
    for row in rows:
        visited_at = row.get("visited_at", "")
        if not visited_at:
            continue

        db.execute(
            "INSERT OR IGNORE INTO safari_history (date, device, visited_at, domain, title, url) VALUES (?, ?, ?, ?, ?, ?)",
            (date, device, visited_at, row.get("domain", ""), row.get("title", ""), row.get("url", "")),
        )
        count += 1

    return count


def _ingest_youtube(db: sqlite3.Connection, date: str, content: str) -> int:
    """Parse and insert YouTube history CSV rows."""
    rows = _parse_csv(content)
    if not rows:
        return 0

    db.execute("DELETE FROM youtube_history WHERE date = ?", (date,))

    count = 0
    for row in rows:
        visited_at = row.get("visited_at", "")
        if not visited_at:
            continue

        db.execute(
            "INSERT OR IGNORE INTO youtube_history (date, visited_at, title, url) VALUES (?, ?, ?, ?)",
            (date, visited_at, row.get("title", ""), row.get("url", "")),
        )
        count += 1

    return count


def _ingest_podcasts(db: sqlite3.Connection, date: str, content: str) -> int:
    """Parse and insert podcast CSV rows."""
    rows = _parse_csv(content)
    if not rows:
        return 0

    db.execute("DELETE FROM podcasts WHERE date = ?", (date,))

    count = 0
    for row in rows:
        episode = row.get("episode") or row.get("title", "")
        podcast = row.get("podcast") or row.get("show", "")
        played_at = row.get("played_at", "")
        if not played_at:
            continue

        try:
            duration_seconds = int(float(row.get("duration_seconds", row.get("duration", 0))))
        except (ValueError, TypeError):
            duration_seconds = 0

        db.execute(
            "INSERT OR IGNORE INTO podcasts (date, episode, podcast, duration_seconds, played_at) VALUES (?, ?, ?, ?, ?)",
            (date, episode, podcast, duration_seconds, played_at),
        )
        count += 1

    return count


def _ingest_claude_sessions(db: sqlite3.Connection, date: str, content: str) -> int:
    """Insert or replace claude sessions markdown."""
    if not content.strip():
        return 0
    db.execute(
        "INSERT OR REPLACE INTO claude_sessions (date, content) VALUES (?, ?)",
        (date, content),
    )
    return 1


def parse_vault_payload(payload: dict) -> int:
    """Parse vault CSV-in-JSON payload and insert into SQLite. Returns total row count."""
    date = payload.get("date", "")
    files = payload.get("files", {})

    if not date:
        log.warning("Vault payload has no date")
        return 0

    log.info("Vault payload received: date=%s, files=%s", date, list(files.keys()))

    db = get_db()
    total_rows = 0

    for filename, content in files.items():
        if not content:
            continue

        if filename in _SCREENTIME_FILES:
            device = _SCREENTIME_FILES[filename]
            n = _ingest_screentime(db, date, device, content)
            log.info("  %s: %d row(s)", filename, n)
            total_rows += n

        elif filename in _SAFARI_FILES:
            device = _SAFARI_FILES[filename]
            n = _ingest_safari(db, date, device, content)
            log.info("  %s: %d row(s)", filename, n)
            total_rows += n

        elif filename == "youtube.csv":
            n = _ingest_youtube(db, date, content)
            log.info("  %s: %d row(s)", filename, n)
            total_rows += n

        elif filename == "podcasts.csv":
            n = _ingest_podcasts(db, date, content)
            log.info("  %s: %d row(s)", filename, n)
            total_rows += n

        elif filename == "claude-sessions.md":
            n = _ingest_claude_sessions(db, date, content)
            log.info("  %s: %d row(s)", filename, n)
            total_rows += n

        else:
            log.warning("  Unknown file: %s (ignored)", filename)

    db.commit()
    log.info("Vault ingest complete: %d row(s) written", total_rows)
    return total_rows
