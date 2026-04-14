"""Health tools: InfluxDB / Apple Health Auto Export client.

Schema notes (discovered from live data):
- All measurements store the value in _field="qty", device in _field="source"
- Measurement names are snake_case with units as suffixes (e.g. step_count_count,
  active_energy_kJ, resting_heart_rate_count/min)
- sleep_phases has a "value" tag per stage: core, deep, rem, awake, asleep
  Each row's _value is aggregate hours for that stage; _time is the wake time
- All data lives in the metrics bucket (no separate workouts bucket)
- Workouts are not currently exported to InfluxDB
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
    import io

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


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------

async def get_sleep(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return sleep summary for the night ending on the given local date.

    Schema: sleep_phases measurement, _field=qty, value tag = stage name
    (core/deep/rem/awake/asleep), _value = aggregate hours, _time = wake time.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'last_night').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    # Sleep spans the previous evening through the morning of local_date.
    # Query 6pm the day before to noon on local_date (local time → UTC).
    prev_day = local_date - timedelta(days=1)
    sleep_start = datetime(prev_day.year, prev_day.month, prev_day.day, 18, 0, tzinfo=tz)
    sleep_end = datetime(local_date.year, local_date.month, local_date.day, 12, 0, tzinfo=tz)
    utc = ZoneInfo("UTC")
    start = sleep_start.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stop = sleep_end.astimezone(utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    flux = f"""
from(bucket: "{INFLUXDB_METRICS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "sleep_phases")
  |> filter(fn: (r) => r._field == "qty")
"""
    rows = await _flux_query(flux)

    if not rows:
        return {
            "date": local_date.isoformat(),
            "bedtime": None,
            "wake_time": None,
            "duration_hours": 0,
        }

    # _time is the wake time (same across all stage rows for one night)
    # _value is hours in that stage; "value" tag is the stage name
    stage_hours: dict[str, float] = {}
    wake_dt: datetime | None = None

    for row in rows:
        stage = row.get("value", "")
        hours = _val(row)
        stage_hours[stage] = stage_hours.get(stage, 0) + hours

        t_str = row.get("_time", "")
        if t_str and wake_dt is None:
            try:
                wake_dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            except ValueError:
                pass

    # Total sleep = core + deep + rem (exclude awake and asleep which is 0/legacy)
    sleep_stages = {s: h for s, h in stage_hours.items() if s not in ("awake", "asleep")}
    total_hours = round(sum(sleep_stages.values()), 1)

    wake_time_str = None
    bedtime_str = None
    if wake_dt:
        wake_local = wake_dt.astimezone(tz)
        wake_time_str = wake_local.strftime("%H:%M")
        # Approximate bedtime by subtracting total sleep + awake time
        awake_hours = stage_hours.get("awake", 0)
        bed_dt = wake_local - timedelta(hours=total_hours + awake_hours)
        bedtime_str = bed_dt.strftime("%H:%M")

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

async def get_activity(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return daily activity summary for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)

    bucket = INFLUXDB_METRICS_BUCKET
    # Use separate queries per measurement and sum — avoids pivot issues with
    # per-minute granularity data.
    flux = f"""
union(tables: [
  from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "step_count_count" and r._field == "qty")
    |> sum()
    |> map(fn: (r) => ({{r with _measurement: "steps"}})),

  from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "active_energy_kJ" and r._field == "qty")
    |> sum()
    |> map(fn: (r) => ({{r with _measurement: "active_energy_kJ"}})),

  from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "apple_exercise_time_min" and r._field == "qty")
    |> sum()
    |> map(fn: (r) => ({{r with _measurement: "exercise_min"}})),

  from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "apple_stand_hour_count" and r._field == "qty")
    |> sum()
    |> map(fn: (r) => ({{r with _measurement: "stand_hours"}})),
])
"""
    rows = await _flux_query(flux)

    result = {
        "date": local_date.isoformat(),
        "steps": 0,
        "active_energy_kcal": 0,
        "exercise_minutes": 0,
        "stand_hours": 0,
    }

    for row in rows:
        measurement = row.get("_measurement", "")
        val = _val(row)
        if measurement == "steps":
            result["steps"] = int(val)
        elif measurement == "active_energy_kJ":
            result["active_energy_kcal"] = round(val / KJ_PER_KCAL)
        elif measurement == "exercise_min":
            result["exercise_minutes"] = round(val)
        elif measurement == "stand_hours":
            result["stand_hours"] = int(val)

    return result


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

async def get_workouts(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return workouts for a given local date.

    Note: Workouts are not currently exported to InfluxDB in this setup.
    Returns an empty list until workout export is configured in Health Auto Export.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    return []


# ---------------------------------------------------------------------------
# Heart rate
# ---------------------------------------------------------------------------

async def get_heart_rate(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return resting heart rate and HRV for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)

    bucket = INFLUXDB_METRICS_BUCKET
    flux = f"""
union(tables: [
  from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "resting_heart_rate_count/min" and r._field == "qty")
    |> mean()
    |> map(fn: (r) => ({{r with _measurement: "rhr"}})),

  from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn: (r) => r._measurement == "heart_rate_variability_ms" and r._field == "qty")
    |> mean()
    |> map(fn: (r) => ({{r with _measurement: "hrv"}})),
])
"""
    rows = await _flux_query(flux)

    result: dict = {"date": local_date.isoformat(), "resting_heart_rate_bpm": None, "hrv_ms": None}
    for row in rows:
        val = _val(row)
        if val == 0:
            continue
        m = row.get("_measurement", "")
        if m == "rhr":
            result["resting_heart_rate_bpm"] = round(val)
        elif m == "hrv":
            result["hrv_ms"] = round(val)

    return result


# ---------------------------------------------------------------------------
# Wellbeing
# ---------------------------------------------------------------------------

async def get_wellbeing(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return mindfulness and state of mind data for a given local date.

    Note: Returns empty if mindfulness/state-of-mind export is not configured
    in Health Auto Export.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)

    return {
        "date": local_date.isoformat(),
        "mindful_minutes": None,
        "state_of_mind": [],
        "note": "Mindfulness/state-of-mind data not yet exported to InfluxDB.",
    }
