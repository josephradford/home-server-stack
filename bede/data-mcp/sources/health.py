"""Health tools: InfluxDB / Apple Health Auto Export client.

Schema notes (discovered from live data):
- metrics bucket: all measurements use _field="qty" for values, _field="source" for device
  Measurement names are snake_case with unit suffixes, e.g.:
    sleep_phases, step_count_count, active_energy_kJ, resting_heart_rate_count/min
  sleep_phases has a "value" tag per stage (core/deep/rem/awake); _value = aggregate hours;
  _time = wake time
- workouts bucket: _measurement="workout", workout_name tag, one row per metric per session
  Fields: duration_min, activeEnergyBurned_kJ, avgHeartRate_bpm, maxHeartRate_bpm, etc.
  heart_rate_data_bpm and heart_rate_recovery_bpm hold per-second HR during the workout.
- state_of_mind and medications: expected in metrics bucket once synced from HAE app;
  measurement names are guesses based on HAE conventions — update when data lands.
"""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .common import DEFAULT_TZ, local_date_to_utc_range, resolve_date

INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://hae-influxdb:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "health")
INFLUXDB_METRICS_BUCKET = os.environ.get("INFLUXDB_METRICS_BUCKET", "metrics")
INFLUXDB_WORKOUTS_BUCKET = os.environ.get("INFLUXDB_WORKOUTS_BUCKET", "workouts")

KJ_PER_KCAL = 4.184


def _auth_headers() -> dict:
    return {"Authorization": f"Token {INFLUXDB_TOKEN}", "Content-Type": "application/vnd.flux"}


async def _flux_query(flux: str) -> list[dict]:
    """Execute a Flux query and return rows as a list of dicts."""
    url = f"{INFLUXDB_URL}/api/v2/query"
    params = {"org": INFLUXDB_ORG}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            url,
            params=params,
            headers=_auth_headers(),
            content=flux.encode(),
        )
        r.raise_for_status()
        return _parse_flux_csv(r.text)


def _parse_flux_csv(text: str) -> list[dict]:
    """Parse InfluxDB annotated CSV into a list of dicts."""
    import csv

    rows: list[dict] = []
    headers: list[str] = []

    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = next(csv.reader([line]))
        if not headers:
            headers = parts
            continue
        if len(parts) == len(headers):
            rows.append(dict(zip(headers, parts)))

    return rows


def _utc_range_flux(local_date: date, tz_name: str) -> tuple[str, str]:
    """Return Flux-formatted UTC start/stop strings for a full local calendar day."""
    start, end = local_date_to_utc_range(local_date, tz_name)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


def _val(row: dict, default: float = 0.0) -> float:
    try:
        return float(row.get("_value", default))
    except (ValueError, TypeError):
        return default


def _local_time(t_str: str, tz: ZoneInfo) -> str:
    """Parse a UTC ISO timestamp and return HH:MM in local timezone."""
    dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
    return dt.astimezone(tz).strftime("%H:%M")


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------

async def get_sleep(date_str: str, timezone: str | None = None) -> dict:
    """Return sleep summary for the night ending on the given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'last_night').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    prev_day = local_date - timedelta(days=1)
    sleep_start = datetime(prev_day.year, prev_day.month, prev_day.day, 18, 0, tzinfo=tz)
    sleep_end = datetime(local_date.year, local_date.month, local_date.day, 12, 0, tzinfo=tz)
    utc = ZoneInfo("UTC")
    start = sleep_start.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stop = sleep_end.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = await _flux_query(f"""
from(bucket: "{INFLUXDB_METRICS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "sleep_phases" and r._field == "qty")
""")

    if not rows:
        return {"date": local_date.isoformat(), "bedtime": None, "wake_time": None, "duration_hours": 0}

    stage_hours: dict[str, float] = {}
    wake_dt: datetime | None = None

    for row in rows:
        stage = row.get("value", "")
        stage_hours[stage] = stage_hours.get(stage, 0) + _val(row)
        if wake_dt is None and row.get("_time"):
            try:
                wake_dt = datetime.fromisoformat(row["_time"].replace("Z", "+00:00"))
            except ValueError:
                pass

    sleep_stages = {s: h for s, h in stage_hours.items() if s not in ("awake", "asleep", "inBed")}
    total_hours = round(sum(sleep_stages.values()), 1)

    wake_time_str = bedtime_str = None
    if wake_dt:
        wake_local = wake_dt.astimezone(tz)
        wake_time_str = wake_local.strftime("%H:%M")
        awake_hours = stage_hours.get("awake", 0)
        bedtime_str = (wake_local - timedelta(hours=total_hours + awake_hours)).strftime("%H:%M")

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

async def get_activity(date_str: str, timezone: str | None = None) -> dict:
    """Return daily activity summary for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)
    b = INFLUXDB_METRICS_BUCKET

    rows = await _flux_query(f"""
union(tables: [
  from(bucket: "{b}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "step_count_count" and r._field == "qty")
    |> sum() |> map(fn: (r) => ({{r with _measurement: "steps"}})),

  from(bucket: "{b}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "active_energy_kJ" and r._field == "qty")
    |> sum() |> map(fn: (r) => ({{r with _measurement: "active_energy_kJ"}})),

  from(bucket: "{b}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "apple_exercise_time_min" and r._field == "qty")
    |> sum() |> map(fn: (r) => ({{r with _measurement: "exercise_min"}})),

  from(bucket: "{b}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "apple_stand_hour_count" and r._field == "qty")
    |> sum() |> map(fn: (r) => ({{r with _measurement: "stand_hours"}})),
])
""")

    result = {"date": local_date.isoformat(), "steps": 0, "active_energy_kcal": 0,
               "exercise_minutes": 0, "stand_hours": 0}
    for row in rows:
        m, val = row.get("_measurement", ""), _val(row)
        if m == "steps":
            result["steps"] = int(val)
        elif m == "active_energy_kJ":
            result["active_energy_kcal"] = round(val / KJ_PER_KCAL)
        elif m == "exercise_min":
            result["exercise_minutes"] = round(val)
        elif m == "stand_hours":
            result["stand_hours"] = int(val)

    return result


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

async def get_workouts(date_str: str, timezone: str | None = None) -> list[dict]:
    """Return workouts for a given local date.

    Schema: workouts bucket, _measurement="workout", workout_name tag.
    One row per metric per session; _time = session start time (UTC).
    Fields: duration_min, activeEnergyBurned_kJ, avgHeartRate_bpm, maxHeartRate_bpm.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)

    rows = await _flux_query(f"""
from(bucket: "{INFLUXDB_WORKOUTS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "workout")
  |> filter(fn: (r) => r._field == "duration_min" or
                       r._field == "activeEnergyBurned_kJ" or
                       r._field == "avgHeartRate_bpm" or
                       r._field == "maxHeartRate_bpm")
  |> pivot(rowKey: ["_time", "workout_name"], columnKey: ["_field"], valueColumn: "_value")
""")

    results: list[dict] = []
    for row in rows:
        t_str = row.get("_time", "")
        start_time = _local_time(t_str, tz) if t_str else ""

        energy_kj = float(row.get("activeEnergyBurned_kJ", 0) or 0)
        results.append({
            "type": row.get("workout_name", "Unknown"),
            "start_time": start_time,
            "duration_minutes": round(float(row.get("duration_min", 0) or 0), 1),
            "energy_kcal": round(energy_kj / KJ_PER_KCAL),
            "avg_heart_rate_bpm": round(float(row.get("avgHeartRate_bpm", 0) or 0)) or None,
            "max_heart_rate_bpm": round(float(row.get("maxHeartRate_bpm", 0) or 0)) or None,
        })

    return results


# ---------------------------------------------------------------------------
# Heart rate
# ---------------------------------------------------------------------------

async def get_heart_rate(date_str: str, timezone: str | None = None) -> dict:
    """Return resting heart rate and HRV for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)
    b = INFLUXDB_METRICS_BUCKET

    rows = await _flux_query(f"""
union(tables: [
  from(bucket: "{b}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "resting_heart_rate_count/min" and r._field == "qty")
    |> mean() |> map(fn: (r) => ({{r with _measurement: "rhr"}})),

  from(bucket: "{b}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "heart_rate_variability_ms" and r._field == "qty")
    |> mean() |> map(fn: (r) => ({{r with _measurement: "hrv"}})),
])
""")

    result: dict = {"date": local_date.isoformat(), "resting_heart_rate_bpm": None, "hrv_ms": None}
    for row in rows:
        val = _val(row)
        if not val:
            continue
        m = row.get("_measurement", "")
        if m == "rhr":
            result["resting_heart_rate_bpm"] = round(val)
        elif m == "hrv":
            result["hrv_ms"] = round(val)

    return result


# ---------------------------------------------------------------------------
# Wellbeing — state of mind + mindfulness
# ---------------------------------------------------------------------------

async def get_wellbeing(date_str: str, timezone: str | None = None) -> dict:
    """Return mindfulness and state of mind data for a given local date.

    Schema (expected — HAE naming convention):
      _measurement="state_of_mind", _field="valence", tag "label"
      _measurement="mindful_minutes", _field="qty"
    Returns empty lists if data hasn't synced from HAE yet.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)
    b = INFLUXDB_METRICS_BUCKET

    rows = await _flux_query(f"""
from(bucket: "{b}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement =~ /state_of_mind|mindful/)
""")

    mindful_minutes = 0
    state_of_mind: list[dict] = []

    for row in rows:
        m = row.get("_measurement", "")
        val = _val(row)
        t_str = row.get("_time", "")
        if "mindful" in m:
            mindful_minutes += val
        elif "state_of_mind" in m:
            entry: dict = {}
            if t_str:
                entry["time"] = _local_time(t_str, tz)
            entry["valence"] = val
            label = row.get("label") or row.get("labels") or row.get("kindLabel") or ""
            if label:
                entry["labels"] = [l.strip() for l in label.split(",") if l.strip()]
            state_of_mind.append(entry)

    return {
        "date": local_date.isoformat(),
        "mindful_minutes": round(mindful_minutes) or None,
        "state_of_mind": state_of_mind,
    }


# ---------------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------------

async def get_medications(date_str: str, timezone: str | None = None) -> list[dict]:
    """Return medications logged on a given local date.

    Schema (expected — HAE naming convention):
      _measurement="medications" or "medication_dose", _field="qty",
      tag "name" = medication name.
    Returns empty list if data hasn't synced from HAE yet.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)

    rows = await _flux_query(f"""
from(bucket: "{INFLUXDB_METRICS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement =~ /[Mm]edication/)
""")

    results: list[dict] = []
    for row in rows:
        t_str = row.get("_time", "")
        results.append({
            "name": row.get("name") or row.get("medication") or row.get("_measurement", ""),
            "time": _local_time(t_str, tz) if t_str else "",
            "qty": _val(row),
            "unit": row.get("unit") or row.get("_field", ""),
        })

    return results
