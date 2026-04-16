"""Vault-based tools: reads data from shared SQLite database.

Screen time, Safari history, YouTube, podcasts, and Claude sessions
are ingested by data-ingest and queried here via SQL.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .common import DEFAULT_TZ, resolve_date
from .db import get_db

logger = logging.getLogger(__name__)


def _to_local(utc_str: str, tz: ZoneInfo) -> str:
    """Convert a UTC datetime string to local ISO8601.

    Handles both 'YYYY-MM-DD HH:MM:SS' (no offset, assumed UTC) and
    'YYYY-MM-DDTHH:MM:SSZ' formats.
    """
    if not utc_str:
        return utc_str
    try:
        cleaned = utc_str.replace("Z", "+00:00")
        # Handle space-separated format without offset (assumed UTC)
        if "T" not in cleaned and "+" not in cleaned and "-" not in cleaned[10:]:
            cleaned = cleaned.replace(" ", "T") + "+00:00"
        dt = datetime.fromisoformat(cleaned)
        return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return utc_str


# ---------------------------------------------------------------------------
# Screen time
# ---------------------------------------------------------------------------

def get_screen_time(
    date_str: str,
    device: str = "mac",
    top_n: int = 20,
    timezone: str | None = None,
) -> dict:
    """Return app and web domain usage for a given local date."""
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    date_iso = local_date.isoformat()

    db = get_db()

    # Build device filter
    if device == "both":
        device_clause = ""
        params: list = [date_iso]
    else:
        device_clause = "AND device = ?"
        params = [date_iso, device]

    apps = db.execute(
        f"SELECT identifier AS name, seconds, device FROM screen_time "
        f"WHERE date = ? {device_clause} AND entry_type = 'app' "
        f"ORDER BY seconds DESC LIMIT ?",
        (*params, top_n),
    ).fetchall()

    web_domains = db.execute(
        f"SELECT identifier AS domain, seconds FROM screen_time "
        f"WHERE date = ? {device_clause} AND entry_type = 'web' "
        f"ORDER BY seconds DESC LIMIT ?",
        (*params, top_n),
    ).fetchall()

    return {
        "date": date_iso,
        "device": device,
        "apps": [{"name": r["name"], "seconds": r["seconds"], "device": r["device"]} for r in apps],
        "web_domains": [{"domain": r["domain"], "seconds": r["seconds"]} for r in web_domains],
    }


# ---------------------------------------------------------------------------
# Safari history
# ---------------------------------------------------------------------------

def get_safari_history(
    date_str: str,
    device: str = "both",
    domain_filter: str | None = None,
    top_n: int = 50,
    timezone: str | None = None,
) -> list[dict]:
    """Return Safari page visits for a given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    date_iso = local_date.isoformat()

    db = get_db()

    clauses = ["date = ?"]
    params: list = [date_iso]

    if device != "both":
        clauses.append("device = ?")
        params.append(device)

    if domain_filter:
        clauses.append("domain LIKE ?")
        params.append(f"%{domain_filter}%")

    where = " AND ".join(clauses)
    params.append(top_n)

    rows = db.execute(
        f"SELECT visited_at, domain, title, url, device FROM safari_history "
        f"WHERE {where} ORDER BY visited_at LIMIT ?",
        params,
    ).fetchall()

    return [
        {
            "visited_at": _to_local(r["visited_at"], tz),
            "domain": r["domain"],
            "title": r["title"],
            "url": r["url"],
            "device": r["device"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# YouTube history (convenience wrapper)
# ---------------------------------------------------------------------------

def get_youtube_history(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return YouTube page visits for a given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    date_iso = local_date.isoformat()

    db = get_db()
    rows = db.execute(
        "SELECT visited_at, title, url FROM youtube_history WHERE date = ? ORDER BY visited_at",
        (date_iso,),
    ).fetchall()

    results = [{"visited_at": _to_local(r["visited_at"], tz), "title": r["title"], "url": r["url"]} for r in rows]

    # Fall back to Safari history filtered to YouTube if youtube_history is empty
    if not results:
        safari = get_safari_history(date_str, device="both", domain_filter="youtube.com", timezone=tz_name)
        results = [{"visited_at": r["visited_at"], "title": r["title"], "url": r["url"]} for r in safari]

    return results


# ---------------------------------------------------------------------------
# Podcasts
# ---------------------------------------------------------------------------

def get_podcasts(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return podcast episodes played on a given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    date_iso = local_date.isoformat()

    db = get_db()
    rows = db.execute(
        "SELECT episode, podcast, duration_seconds, played_at FROM podcasts WHERE date = ? ORDER BY played_at",
        (date_iso,),
    ).fetchall()

    return [
        {
            "episode": r["episode"],
            "podcast": r["podcast"],
            "duration_minutes": round(r["duration_seconds"] / 60, 1) if r["duration_seconds"] else 0,
            "played_at": _to_local(r["played_at"], tz),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Claude sessions
# ---------------------------------------------------------------------------

def get_claude_sessions(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return Claude Code session summaries for a given local date."""
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    date_iso = local_date.isoformat()

    db = get_db()
    rows = db.execute(
        "SELECT project, start_time, end_time, duration_min, turns, summary "
        "FROM claude_sessions WHERE date = ? ORDER BY start_time",
        (date_iso,),
    ).fetchall()

    return [
        {
            "project": r["project"],
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "duration_minutes": r["duration_min"],
            "turns": r["turns"],
            "summary": r["summary"],
        }
        for r in rows
    ]


def get_bede_sessions(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return Bede session summaries for a given local date."""
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    date_iso = local_date.isoformat()

    db = get_db()
    rows = db.execute(
        "SELECT project, start_time, end_time, duration_min, turns, summary "
        "FROM bede_sessions WHERE date = ? ORDER BY start_time",
        (date_iso,),
    ).fetchall()

    return [
        {
            "project": r["project"],
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "duration_minutes": r["duration_min"],
            "turns": r["turns"],
            "summary": r["summary"],
        }
        for r in rows
    ]
