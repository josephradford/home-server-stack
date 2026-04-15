"""Parse Health Auto Export JSON payloads into SQLite rows.

HAE payload structure (from irvinlim/apple-health-ingester Go structs):

    {
      "data": {
        "metrics": [
          {
            "name": "step_count",
            "units": "count",
            "data": [{"date": "2026-04-14 06:00:00 +1000", "qty": 8423, "source": "iPhone"}],
            "aggregatedSleepAnalyses": [...]
          }
        ],
        "workouts": [
          {
            "name": "Running",
            "start": "2026-04-14 06:30:00 +1000",
            "end": "2026-04-14 07:00:00 +1000",
            ...
          }
        ]
      }
    }

Timestamps arrive as "YYYY-MM-DD HH:MM:SS +HHMM" (local with offset).
We store: local date (YYYY-MM-DD) and UTC ISO8601 recorded_at.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

from db import get_db

log = logging.getLogger(__name__)

# HAE timestamp formats — try multiple patterns
_TS_PATTERNS = [
    r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{4})",  # "2026-04-14 06:00:00 +1000"
    r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2})",  # ISO8601
]

# Metrics that map to dedicated tables rather than the generic health_metrics
_SLEEP_METRIC = "sleep_analysis"
_STATE_OF_MIND_PATTERNS = re.compile(r"state.of.mind", re.IGNORECASE)
_MEDICATION_PATTERNS = re.compile(r"medication", re.IGNORECASE)


def _parse_hae_timestamp(ts_str: str) -> tuple[str, str] | None:
    """Parse HAE timestamp to (local_date, utc_iso8601).

    Returns None if parsing fails.
    """
    if not ts_str:
        return None

    for pattern in _TS_PATTERNS:
        m = re.match(pattern, ts_str.strip())
        if m:
            date_part, time_part, offset = m.groups()
            # Normalise offset: "+1000" -> "+10:00"
            if ":" not in offset:
                offset = offset[:3] + ":" + offset[3:]
            iso_str = f"{date_part}T{time_part}{offset}"
            try:
                dt = datetime.fromisoformat(iso_str)
                local_date = dt.strftime("%Y-%m-%d")
                utc_iso = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                return local_date, utc_iso
            except ValueError:
                continue

    # Fallback: try direct fromisoformat
    try:
        dt = datetime.fromisoformat(ts_str.strip())
        local_date = dt.strftime("%Y-%m-%d")
        utc_iso = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return local_date, utc_iso
    except ValueError:
        log.warning("Could not parse HAE timestamp: %s", ts_str)
        return None


def _insert_health_metric(db: sqlite3.Connection, date: str, metric: str, value: float, source: str | None, recorded_at: str) -> int:
    """Insert a single health metric row. Returns 1 if inserted, 0 if duplicate."""
    try:
        db.execute(
            "INSERT OR IGNORE INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (date, metric, value, source, recorded_at),
        )
        return db.total_changes  # will be checked via delta
    except sqlite3.Error as e:
        log.warning("Failed to insert health metric %s: %s", metric, e)
        return 0


def _process_sleep(db: sqlite3.Connection, metric: dict) -> int:
    """Process sleep_analysis metric.

    HAE sends sleep data in one of three locations:
    - aggregatedSleepAnalyses[] (aggregated format)
    - sleepAnalyses[] (non-aggregated format)
    - data[] (inline format — stage hours as fields on each entry)
    """
    rows = 0
    analyses = metric.get("aggregatedSleepAnalyses", [])
    if not analyses:
        analyses = metric.get("sleepAnalyses", [])
    if not analyses:
        # HAE sends sleep data inline in the regular data[] array
        analyses = metric.get("data", [])

    for analysis in analyses:
        # Parse sleep start/end times
        sleep_start_ts = _parse_hae_timestamp(analysis.get("sleepStart", "") or analysis.get("startDate", ""))
        sleep_end_ts = _parse_hae_timestamp(analysis.get("sleepEnd", "") or analysis.get("endDate", ""))

        # Use sleep end date as the canonical date (morning of wake-up)
        date = sleep_end_ts[0] if sleep_end_ts else (sleep_start_ts[0] if sleep_start_ts else None)
        if not date:
            continue

        sleep_start_utc = sleep_start_ts[1] if sleep_start_ts else None
        sleep_end_utc = sleep_end_ts[1] if sleep_end_ts else None
        source = analysis.get("source") or analysis.get("sleepSource", "")

        # Aggregated format has named stage fields (core, deep, rem, awake, inBed, asleep)
        stages = {}
        for stage_name in ("core", "deep", "rem", "awake", "inBed", "asleep"):
            val = analysis.get(stage_name)
            if val is not None and val != 0:
                try:
                    stages[stage_name] = float(val)
                except (ValueError, TypeError):
                    pass

        # Non-aggregated format has "value" field with stage name
        if not stages and "value" in analysis:
            stage = analysis["value"]
            qty = analysis.get("qty")
            if stage and qty is not None:
                try:
                    stages[stage] = float(qty)
                except (ValueError, TypeError):
                    pass

        for stage, hours in stages.items():
            try:
                db.execute(
                    "INSERT OR REPLACE INTO sleep_phases (date, stage, hours, sleep_start, sleep_end, source) VALUES (?, ?, ?, ?, ?, ?)",
                    (date, stage, hours, sleep_start_utc, sleep_end_utc, source or None),
                )
                rows += 1
            except sqlite3.Error as e:
                log.warning("Failed to insert sleep phase %s: %s", stage, e)

    return rows


def _process_state_of_mind(db: sqlite3.Connection, metric: dict) -> int:
    """Process state_of_mind metric."""
    rows = 0
    for dp in metric.get("data", []):
        parsed = _parse_hae_timestamp(dp.get("date", ""))
        if not parsed:
            continue
        date, utc_iso = parsed
        valence = dp.get("qty")
        # Labels may come as various fields
        labels = dp.get("label") or dp.get("labels") or dp.get("kindLabel")
        if isinstance(labels, list):
            labels = json.dumps(labels)
        elif isinstance(labels, str) and labels:
            labels = json.dumps([l.strip() for l in labels.split(",") if l.strip()])
        else:
            labels = None
        context = dp.get("context", None)

        try:
            db.execute(
                "INSERT OR IGNORE INTO state_of_mind (date, recorded_at, valence, labels, context) VALUES (?, ?, ?, ?, ?)",
                (date, utc_iso, valence, labels, context),
            )
            rows += 1
        except sqlite3.Error as e:
            log.warning("Failed to insert state_of_mind: %s", e)
    return rows


def _process_medications(db: sqlite3.Connection, metric: dict) -> int:
    """Process medication metric."""
    rows = 0
    med_name = metric.get("name", "unknown")
    units = metric.get("units", "")

    for dp in metric.get("data", []):
        parsed = _parse_hae_timestamp(dp.get("date", ""))
        if not parsed:
            continue
        date, utc_iso = parsed
        qty = dp.get("qty")

        try:
            db.execute(
                "INSERT OR IGNORE INTO medications (date, name, quantity, unit, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (date, med_name, qty, units or None, utc_iso),
            )
            rows += 1
        except sqlite3.Error as e:
            log.warning("Failed to insert medication %s: %s", med_name, e)
    return rows


def _process_generic_metric(db: sqlite3.Connection, metric: dict) -> int:
    """Process a standard metric with data[] array of {date, qty, source}."""
    rows = 0
    name = metric.get("name", "unknown")
    units = metric.get("units", "")
    # Store metric name with units for clarity (e.g. "active_energy_kJ")
    metric_key = f"{name}_{units}" if units and units not in name else name

    for dp in metric.get("data", []):
        parsed = _parse_hae_timestamp(dp.get("date", ""))
        if not parsed:
            continue
        date, utc_iso = parsed
        qty = dp.get("qty")
        if qty is None:
            continue
        try:
            value = float(qty)
        except (ValueError, TypeError):
            continue

        source = dp.get("source", None)
        try:
            db.execute(
                "INSERT OR IGNORE INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (date, metric_key, value, source, utc_iso),
            )
            rows += 1
        except sqlite3.Error as e:
            log.warning("Failed to insert metric %s: %s", metric_key, e)

    return rows


def _process_workouts(db: sqlite3.Connection, workouts: list) -> int:
    """Process workout entries."""
    rows = 0
    for w in workouts:
        name = w.get("name", "Unknown")
        start_ts = _parse_hae_timestamp(w.get("start", ""))
        end_ts = _parse_hae_timestamp(w.get("end", ""))
        if not start_ts:
            log.warning("Workout %s has no start time, skipping", name)
            continue

        date, start_utc = start_ts
        end_utc = end_ts[1] if end_ts else None

        # Duration: HAE may provide it directly or we compute from start/end
        duration_min = None
        if "duration" in w:
            try:
                duration_min = float(w["duration"]) / 60.0  # HAE sends seconds
            except (ValueError, TypeError):
                pass

        # Energy
        active_energy_kj = None
        energy_val = w.get("activeEnergy") or w.get("activeEnergyBurned")
        if energy_val is not None:
            try:
                active_energy_kj = float(energy_val)
            except (ValueError, TypeError):
                pass

        # Heart rate
        avg_hr = None
        max_hr = None
        try:
            avg_hr = float(w["avgHeartRate"]) if w.get("avgHeartRate") else None
        except (ValueError, TypeError):
            pass
        try:
            max_hr = float(w["maxHeartRate"]) if w.get("maxHeartRate") else None
        except (ValueError, TypeError):
            pass

        try:
            db.execute(
                "INSERT OR IGNORE INTO workouts (date, workout_name, start_time, end_time, duration_min, active_energy_kj, avg_heart_rate_bpm, max_heart_rate_bpm) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (date, name, start_utc, end_utc, duration_min, active_energy_kj, avg_hr, max_hr),
            )
            rows += 1
        except sqlite3.Error as e:
            log.warning("Failed to insert workout %s: %s", name, e)

    return rows


def parse_health_payload(payload: dict) -> int:
    """Parse HAE JSON and insert into SQLite. Returns total row count."""
    data = payload.get("data", {})
    metrics = data.get("metrics", [])
    workouts = data.get("workouts", [])

    log.info(
        "Health payload received: %d metric(s), %d workout(s)",
        len(metrics),
        len(workouts),
    )

    db = get_db()
    total_before = db.total_changes
    total_rows = 0

    for metric in metrics:
        name = metric.get("name", "unknown")
        log.info("  Processing metric: %s", name)

        if name == _SLEEP_METRIC or metric.get("aggregatedSleepAnalyses") or metric.get("sleepAnalyses"):
            total_rows += _process_sleep(db, metric)
        elif _STATE_OF_MIND_PATTERNS.search(name):
            total_rows += _process_state_of_mind(db, metric)
        elif _MEDICATION_PATTERNS.search(name):
            total_rows += _process_medications(db, metric)
        else:
            total_rows += _process_generic_metric(db, metric)

    total_rows += _process_workouts(db, workouts)

    db.commit()
    log.info("Health ingest complete: %d row(s) written", total_rows)
    return total_rows
