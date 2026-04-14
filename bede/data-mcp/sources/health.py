"""Health tools: InfluxDB / Apple Health Auto Export client."""

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .common import DEFAULT_TZ, fmt_time, local_date_to_utc_range, resolve_date

INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://hae-influxdb:8086")
INFLUXDB_TOKEN = os.environ.get("INFLUXDB_TOKEN", "")
INFLUXDB_ORG = os.environ.get("INFLUXDB_ORG", "health")
INFLUXDB_METRICS_BUCKET = os.environ.get("INFLUXDB_METRICS_BUCKET", "metrics")
INFLUXDB_WORKOUTS_BUCKET = os.environ.get("INFLUXDB_WORKOUTS_BUCKET", "workouts")


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
        # Parse annotated CSV response
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
            row = dict(zip(headers, parts))
            rows.append(row)

    return rows


def _utc_range_flux(local_date: date, tz_name: str) -> tuple[str, str]:
    """Return Flux-formatted UTC start/stop strings for a local day."""
    start, end = local_date_to_utc_range(local_date, tz_name)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")


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
    flux = f"""
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "StepCount" or
                       r._measurement == "ActiveEnergyBurned" or
                       r._measurement == "AppleExerciseTime" or
                       r._measurement == "AppleMoveTime" or
                       r._measurement == "AppleStandHour")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["_measurement"])
  |> sum(column: "_value")
"""
    rows = await _flux_query(flux)

    result = {
        "date": local_date.isoformat(),
        "steps": 0,
        "active_energy_kcal": 0,
        "exercise_minutes": 0,
        "move_minutes": 0,
        "stand_hours": 0,
    }

    for row in rows:
        measurement = row.get("_measurement", "")
        try:
            val = float(row.get("_value", 0))
        except (ValueError, TypeError):
            val = 0.0
        if measurement == "StepCount":
            result["steps"] = int(val)
        elif measurement == "ActiveEnergyBurned":
            result["active_energy_kcal"] = round(val)
        elif measurement == "AppleExerciseTime":
            result["exercise_minutes"] = round(val)
        elif measurement == "AppleMoveTime":
            result["move_minutes"] = round(val)
        elif measurement == "AppleStandHour":
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

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)

    bucket = INFLUXDB_WORKOUTS_BUCKET
    flux = f"""
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._field == "value" or r._field == "duration" or r._field == "totalEnergyBurned")
  |> pivot(rowKey: ["_time", "workoutActivityType"], columnKey: ["_field"], valueColumn: "_value")
"""
    rows = await _flux_query(flux)

    tz = ZoneInfo(tz_name)
    results: list[dict] = []
    for row in rows:
        workout_type = row.get("workoutActivityType", row.get("_measurement", "Unknown"))
        t_str = row.get("_time", "")
        try:
            dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            start_time = dt.astimezone(tz).strftime("%H:%M")
        except (ValueError, AttributeError):
            start_time = ""

        try:
            duration = round(float(row.get("duration", 0)) / 60, 1)
        except (ValueError, TypeError):
            duration = 0.0
        try:
            energy = round(float(row.get("totalEnergyBurned", 0)))
        except (ValueError, TypeError):
            energy = 0

        results.append({
            "type": workout_type,
            "start_time": start_time,
            "duration_minutes": duration,
            "energy_kcal": energy,
        })

    return results


# ---------------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------------

async def get_sleep(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return sleep summary for the night ending on the given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'last_night').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    # Sleep spans the previous evening through the morning of local_date
    # Query from 6 PM the day before to noon on local_date
    prev_day = local_date - timedelta(days=1)
    sleep_start_utc = datetime(
        prev_day.year, prev_day.month, prev_day.day, 18, 0, tzinfo=tz
    ).astimezone(ZoneInfo("UTC"))
    sleep_end_utc = datetime(
        local_date.year, local_date.month, local_date.day, 12, 0, tzinfo=tz
    ).astimezone(ZoneInfo("UTC"))

    start = sleep_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    stop = sleep_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    flux = f"""
from(bucket: "{INFLUXDB_METRICS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "SleepAnalysis")
  |> filter(fn: (r) => r._field == "value")
  |> sort(columns: ["_time"])
"""
    rows = await _flux_query(flux)

    if not rows:
        return {"date": local_date.isoformat(), "bedtime": None, "wake_time": None, "duration_hours": 0}

    # Find earliest and latest timestamps and sum asleep durations
    times: list[datetime] = []
    total_asleep_seconds = 0.0

    for row in rows:
        t_str = row.get("_time", "")
        try:
            dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            times.append(dt)
        except (ValueError, AttributeError):
            continue

        # HAE stores HKCategoryValueSleepAnalysisAsleep = 1 (or similar)
        # Sum values assuming each row represents 1-minute resolution
        try:
            val = float(row.get("_value", 0))
            # If value is 0/1 flag (per-minute), each row = 1 minute
            if 0 <= val <= 1:
                total_asleep_seconds += val * 60
            else:
                # If value is duration in seconds
                total_asleep_seconds += val
        except (ValueError, TypeError):
            pass

    if not times:
        return {"date": local_date.isoformat(), "bedtime": None, "wake_time": None, "duration_hours": 0}

    bedtime = min(times).astimezone(tz).strftime("%H:%M")
    wake_time = max(times).astimezone(tz).strftime("%H:%M")
    total_hours = round(total_asleep_seconds / 3600, 1) if total_asleep_seconds > 0 else round(
        (max(times) - min(times)).total_seconds() / 3600, 1
    )

    return {
        "date": local_date.isoformat(),
        "bedtime": bedtime,
        "wake_time": wake_time,
        "duration_hours": total_hours,
    }


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

    flux = f"""
from(bucket: "{INFLUXDB_METRICS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "RestingHeartRate" or
                       r._measurement == "HeartRateVariabilitySDNN")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["_measurement"])
  |> mean(column: "_value")
"""
    rows = await _flux_query(flux)

    result = {"date": local_date.isoformat(), "resting_heart_rate_bpm": None, "hrv_ms": None}
    for row in rows:
        measurement = row.get("_measurement", "")
        try:
            val = round(float(row.get("_value", 0)))
        except (ValueError, TypeError):
            val = None
        if measurement == "RestingHeartRate":
            result["resting_heart_rate_bpm"] = val
        elif measurement == "HeartRateVariabilitySDNN":
            result["hrv_ms"] = val

    return result


# ---------------------------------------------------------------------------
# Wellbeing
# ---------------------------------------------------------------------------

async def get_wellbeing(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return mindfulness and state of mind data for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)
    start, stop = _utc_range_flux(local_date, tz_name)

    flux = f"""
from(bucket: "{INFLUXDB_METRICS_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "MindfulSession" or
                       r._measurement == "StateOfMind")
  |> filter(fn: (r) => r._field == "value" or r._field == "valenceClassification")
  |> sort(columns: ["_time"])
"""
    rows = await _flux_query(flux)

    mindful_minutes = 0.0
    state_of_mind: list[dict] = []

    for row in rows:
        measurement = row.get("_measurement", "")
        t_str = row.get("_time", "")
        try:
            dt = datetime.fromisoformat(t_str.replace("Z", "+00:00")).astimezone(tz)
            time_str = dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            time_str = ""

        if measurement == "MindfulSession":
            try:
                mindful_minutes += float(row.get("_value", 0)) / 60
            except (ValueError, TypeError):
                pass
        elif measurement == "StateOfMind":
            try:
                valence = float(row.get("_value", row.get("valenceClassification", 0)))
            except (ValueError, TypeError):
                valence = 0
            labels_raw = row.get("labels", "")
            labels = [l.strip() for l in labels_raw.split(",") if l.strip()] if labels_raw else []
            state_of_mind.append({"time": time_str, "valence": valence, "labels": labels})

    return {
        "date": local_date.isoformat(),
        "mindful_minutes": round(mindful_minutes),
        "state_of_mind": state_of_mind,
    }
