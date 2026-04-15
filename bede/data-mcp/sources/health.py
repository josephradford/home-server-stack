"""Health tools: SQLite-backed Apple Health data queries.

Reads from the shared SQLite database populated by data-ingest.
All timestamps stored as UTC ISO8601; converted to local time for display.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .common import DEFAULT_TZ, resolve_date
from .db import get_db

KJ_PER_KCAL = 4.184


def _local_time(utc_iso: str, tz: ZoneInfo) -> str:
    """Parse a UTC ISO timestamp and return HH:MM in local timezone."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    return dt.astimezone(tz).strftime("%H:%M")


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------

def get_sleep(date_str: str, timezone: str | None = None) -> dict:
    """Return sleep summary for the night ending on the given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    db = get_db()
    rows = db.execute(
        "SELECT stage, hours, sleep_start, sleep_end, source FROM sleep_phases WHERE date = ?",
        (local_date.isoformat(),),
    ).fetchall()

    if not rows:
        return {"date": local_date.isoformat(), "bedtime": None, "wake_time": None, "duration_hours": 0}

    sleep_stages = {}
    sleep_start_utc = None
    sleep_end_utc = None

    for row in rows:
        stage = row["stage"]
        if stage not in ("awake", "asleep", "inBed"):
            sleep_stages[stage] = row["hours"]
        if row["sleep_start"] and not sleep_start_utc:
            sleep_start_utc = row["sleep_start"]
        if row["sleep_end"] and not sleep_end_utc:
            sleep_end_utc = row["sleep_end"]

    total_hours = round(sum(sleep_stages.values()), 1)

    bedtime_str = wake_time_str = None
    if sleep_start_utc:
        bedtime_str = _local_time(sleep_start_utc, tz)
    if sleep_end_utc:
        wake_time_str = _local_time(sleep_end_utc, tz)

    # Fallback: derive bedtime from wake_time - total sleep - awake hours
    if not bedtime_str and wake_time_str and sleep_end_utc:
        awake_hours = sum(r["hours"] for r in rows if r["stage"] == "awake")
        wake_dt = datetime.fromisoformat(sleep_end_utc.replace("Z", "+00:00"))
        bed_dt = wake_dt - timedelta(hours=total_hours + awake_hours)
        bedtime_str = bed_dt.astimezone(tz).strftime("%H:%M")

    return {
        "date": local_date.isoformat(),
        "bedtime": bedtime_str,
        "wake_time": wake_time_str,
        "duration_hours": total_hours,
        "stages": {s: round(h, 2) for s, h in sleep_stages.items()},
    }


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def get_activity(date_str: str, timezone: str | None = None) -> dict:
    """Return daily activity summary for a given local date."""
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)

    db = get_db()
    rows = db.execute(
        """SELECT metric, SUM(value) as total
           FROM health_metrics
           WHERE date = ? AND metric IN ('step_count', 'active_energy', 'active_energy_kJ',
                                          'apple_exercise_time', 'apple_exercise_time_min',
                                          'apple_stand_hour', 'apple_stand_hour_count',
                                          'apple_move_time', 'apple_move_time_min')
           GROUP BY metric""",
        (local_date.isoformat(),),
    ).fetchall()

    result = {
        "date": local_date.isoformat(),
        "steps": 0,
        "active_energy_kcal": 0,
        "exercise_minutes": 0,
        "stand_hours": 0,
    }

    for row in rows:
        m, val = row["metric"], row["total"]
        if "step_count" in m:
            result["steps"] = int(val)
        elif "active_energy" in m:
            result["active_energy_kcal"] = round(val / KJ_PER_KCAL)
        elif "exercise_time" in m:
            result["exercise_minutes"] = round(val)
        elif "stand_hour" in m:
            result["stand_hours"] = int(val)

    return result


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

def get_workouts(date_str: str, timezone: str | None = None) -> list[dict]:
    """Return workouts for a given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    db = get_db()
    rows = db.execute(
        "SELECT * FROM workouts WHERE date = ? ORDER BY start_time",
        (local_date.isoformat(),),
    ).fetchall()

    results = []
    for row in rows:
        energy_kj = row["active_energy_kj"] or 0
        results.append({
            "type": row["workout_name"],
            "start_time": _local_time(row["start_time"], tz) if row["start_time"] else "",
            "duration_minutes": round(row["duration_min"], 1) if row["duration_min"] else None,
            "energy_kcal": round(energy_kj / KJ_PER_KCAL) if energy_kj else None,
            "avg_heart_rate_bpm": round(row["avg_heart_rate_bpm"]) if row["avg_heart_rate_bpm"] else None,
            "max_heart_rate_bpm": round(row["max_heart_rate_bpm"]) if row["max_heart_rate_bpm"] else None,
        })

    return results


# ---------------------------------------------------------------------------
# Heart rate
# ---------------------------------------------------------------------------

def get_heart_rate(date_str: str, timezone: str | None = None) -> dict:
    """Return resting heart rate and HRV for a given local date."""
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)

    db = get_db()
    rows = db.execute(
        """SELECT metric, AVG(value) as avg_val
           FROM health_metrics
           WHERE date = ? AND metric IN ('resting_heart_rate', 'resting_heart_rate_count/min',
                                          'heart_rate_variability', 'heart_rate_variability_ms')
           GROUP BY metric""",
        (local_date.isoformat(),),
    ).fetchall()

    result: dict = {"date": local_date.isoformat(), "resting_heart_rate_bpm": None, "hrv_ms": None}
    for row in rows:
        val = row["avg_val"]
        if not val:
            continue
        m = row["metric"]
        if "resting_heart_rate" in m:
            result["resting_heart_rate_bpm"] = round(val)
        elif "heart_rate_variability" in m:
            result["hrv_ms"] = round(val)

    return result


# ---------------------------------------------------------------------------
# Wellbeing — state of mind + mindfulness
# ---------------------------------------------------------------------------

def get_wellbeing(date_str: str, timezone: str | None = None) -> dict:
    """Return mindfulness and state of mind data for a given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    db = get_db()

    # Mindful minutes from health_metrics
    mindful_row = db.execute(
        """SELECT SUM(value) as total
           FROM health_metrics
           WHERE date = ? AND metric LIKE '%mindful%'""",
        (local_date.isoformat(),),
    ).fetchone()
    mindful_minutes = round(mindful_row["total"]) if mindful_row and mindful_row["total"] else None

    # State of mind entries
    som_rows = db.execute(
        "SELECT recorded_at, valence, labels, context FROM state_of_mind WHERE date = ? ORDER BY recorded_at",
        (local_date.isoformat(),),
    ).fetchall()

    state_of_mind = []
    for row in som_rows:
        entry: dict = {}
        if row["recorded_at"]:
            entry["time"] = _local_time(row["recorded_at"], tz)
        if row["valence"] is not None:
            entry["valence"] = row["valence"]
        if row["labels"]:
            try:
                entry["labels"] = json.loads(row["labels"])
            except (json.JSONDecodeError, TypeError):
                entry["labels"] = [l.strip() for l in row["labels"].split(",") if l.strip()]
        if row["context"]:
            entry["context"] = row["context"]
        state_of_mind.append(entry)

    return {
        "date": local_date.isoformat(),
        "mindful_minutes": mindful_minutes,
        "state_of_mind": state_of_mind,
    }


# ---------------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------------

def get_medications(date_str: str, timezone: str | None = None) -> list[dict]:
    """Return medications logged on a given local date."""
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    db = get_db()
    rows = db.execute(
        "SELECT name, quantity, unit, recorded_at FROM medications WHERE date = ? ORDER BY recorded_at",
        (local_date.isoformat(),),
    ).fetchall()

    return [
        {
            "name": row["name"],
            "time": _local_time(row["recorded_at"], tz) if row["recorded_at"] else "",
            "qty": row["quantity"],
            "unit": row["unit"],
        }
        for row in rows
    ]
