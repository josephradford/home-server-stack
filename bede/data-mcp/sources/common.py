"""Shared utilities: date resolution and timezone conversion."""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TZ = os.environ.get("DEFAULT_TIMEZONE", "Australia/Sydney")


def resolve_date(date_str: str, tz_name: str | None = None) -> date:
    """Resolve 'today', 'yesterday', 'last_night', or 'YYYY-MM-DD' to a local date."""
    tz_name = tz_name or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if date_str in ("today", "last_night"):
        return today
    if date_str == "yesterday":
        return today - timedelta(days=1)
    return date.fromisoformat(date_str)


def local_date_to_utc_range(local_date: date, tz_name: str) -> tuple[datetime, datetime]:
    """Return UTC start and end datetimes for a local calendar day."""
    tz = ZoneInfo(tz_name)
    start = datetime(local_date.year, local_date.month, local_date.day, tzinfo=tz)
    end = start + timedelta(days=1)
    utc = ZoneInfo("UTC")
    return start.astimezone(utc), end.astimezone(utc)


def fmt_time(ts: float | datetime, tz_name: str) -> str:
    """Format a Unix timestamp or UTC datetime as HH:MM in local timezone."""
    tz = ZoneInfo(tz_name)
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC"))
    else:
        dt = ts
    return dt.astimezone(tz).strftime("%H:%M")


def fmt_datetime(ts: float | datetime, tz_name: str) -> str:
    """Format a Unix timestamp or UTC datetime as ISO8601 in local timezone."""
    tz = ZoneInfo(tz_name)
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC"))
    else:
        dt = ts
    return dt.astimezone(tz).isoformat(timespec="seconds")


def parse_utc_iso(s: str) -> datetime:
    """Parse a UTC ISO8601 string (with or without Z suffix) to a UTC datetime."""
    s = s.rstrip("Z").replace("+00:00", "")
    # Handle space separator as well as T
    s = s.replace(" ", "T")
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=ZoneInfo("UTC"))
