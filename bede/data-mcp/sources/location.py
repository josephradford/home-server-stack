"""Location tools: OwnTracks Recorder client with clustering and geocoding."""

import math
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .common import DEFAULT_TZ, fmt_time, local_date_to_utc_range, resolve_date

OWNTRACKS_URL = os.environ.get("OWNTRACKS_URL", "http://owntracks-recorder:8083")
OWNTRACKS_USER = os.environ.get("OWNTRACKS_USER", "")
OWNTRACKS_DEVICE = os.environ.get("OWNTRACKS_DEVICE", "")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "data-mcp/1.0 (home-server-stack; personal use)"

# In-memory geocoding cache: (lat_rounded, lon_rounded) -> place string
_geocache: dict[tuple[float, float], dict] = {}

CLUSTER_RADIUS_KM = 0.2  # 200 m
CLUSTER_GAP_MINUTES = 5  # start new cluster if gap > 5 min between consecutive points
MIN_STOP_MINUTES = 3     # ignore clusters shorter than this


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _centroid(points: list[dict]) -> tuple[float, float]:
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    return sum(lats) / len(lats), sum(lons) / len(lons)


async def _fetch_points(from_date: date, to_date: date) -> list[dict]:
    """Fetch raw OwnTracks points for a UTC date range."""
    if not OWNTRACKS_USER or not OWNTRACKS_DEVICE:
        raise RuntimeError(
            "OWNTRACKS_USER and OWNTRACKS_DEVICE must be set in the environment."
        )
    params = {
        "user": OWNTRACKS_USER,
        "device": OWNTRACKS_DEVICE,
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{OWNTRACKS_URL}/api/0/locations", params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("data", [])


async def _reverse_geocode(lat: float, lon: float) -> dict:
    """Reverse geocode a coordinate via Nominatim with caching."""
    key = (round(lat, 4), round(lon, 4))
    if key in _geocache:
        return _geocache[key]

    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json"},
        )
        r.raise_for_status()
        geo = r.json()

    _geocache[key] = geo
    return geo


def _extract_place(geo: dict) -> tuple[str, str]:
    """Return (place, address) from a Nominatim response."""
    name = geo.get("name", "") or geo.get("namedetails", {}).get("name", "")
    addr = geo.get("address", {})
    suburb = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or ""
    city = addr.get("city") or addr.get("town") or addr.get("village") or ""
    state = addr.get("state", "")
    postcode = addr.get("postcode", "")

    place = name if name else suburb
    parts = [p for p in [suburb, city, state, postcode] if p]
    address = ", ".join(parts) if parts else geo.get("display_name", "")

    return place or "Unknown", address


def _cluster_points(points: list[dict], tz: ZoneInfo) -> list[list[dict]]:
    """Group sorted points into clusters by proximity and time gap."""
    if not points:
        return []

    # Sort by timestamp
    pts = sorted(points, key=lambda p: p["tst"])
    clusters: list[list[dict]] = []
    current: list[dict] = [pts[0]]

    for p in pts[1:]:
        c_lat, c_lon = _centroid(current)
        dist = _haversine_km(c_lat, c_lon, p["lat"], p["lon"])
        gap_minutes = (p["tst"] - current[-1]["tst"]) / 60

        if dist <= CLUSTER_RADIUS_KM and gap_minutes <= CLUSTER_GAP_MINUTES:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]

    clusters.append(current)
    return clusters


def _activity_label(velocity_kmh: float | None) -> str:
    if velocity_kmh is None:
        return "stationary"
    if velocity_kmh < 3:
        return "stationary"
    if velocity_kmh < 12:
        return "walking"
    if velocity_kmh < 50:
        return "cycling"
    return "driving"


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

async def get_location_summary(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return summarised stops for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name (default: DEFAULT_TIMEZONE env var).
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    local_date = resolve_date(date_str, tz_name)

    # Query one extra day on each side to capture the full local day in UTC
    utc_from = local_date - timedelta(days=1)
    utc_to = local_date + timedelta(days=1)
    utc_start, utc_end = local_date_to_utc_range(local_date, tz_name)

    raw = await _fetch_points(utc_from, utc_to)

    # Filter to points that fall within the local calendar day
    def in_local_day(p: dict) -> bool:
        dt = datetime.fromtimestamp(p["tst"], tz=ZoneInfo("UTC")).astimezone(tz)
        return dt.date() == local_date

    points = [p for p in raw if in_local_day(p)]

    if not points:
        return {"date": local_date.isoformat(), "timezone": tz_name, "stops": []}

    clusters = _cluster_points(points, tz)

    stops: list[dict] = []
    for cluster in clusters:
        duration_minutes = (cluster[-1]["tst"] - cluster[0]["tst"]) / 60
        if len(cluster) < 2 and duration_minutes < MIN_STOP_MINUTES:
            continue  # single point / very short — transit noise

        c_lat, c_lon = _centroid(cluster)
        geo = await _reverse_geocode(c_lat, c_lon)
        place, address = _extract_place(geo)

        # Activity: use median velocity across the cluster
        velocities = [p.get("vel") for p in cluster if p.get("vel") is not None]
        avg_vel = sum(velocities) / len(velocities) if velocities else 0
        activity = _activity_label(avg_vel)

        arrived = fmt_time(cluster[0]["tst"], tz_name)
        departed = fmt_time(cluster[-1]["tst"], tz_name)

        # Only add if arrived != departed (not a single snapshot)
        stops.append({
            "place": place,
            "address": address,
            "arrived": arrived,
            "departed": departed,
            "activity": activity,
        })

    return {
        "date": local_date.isoformat(),
        "timezone": tz_name,
        "stops": stops,
    }


async def get_location_raw(
    from_date: str,
    to_date: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return raw GPS points for a local date range without summarisation.

    Args:
        from_date: Start local date ('YYYY-MM-DD').
        to_date: End local date ('YYYY-MM-DD').
        timezone: Olson timezone name.
    """
    tz_name = timezone or DEFAULT_TZ
    tz = ZoneInfo(tz_name)
    d_from = resolve_date(from_date, tz_name)
    d_to = resolve_date(to_date, tz_name)

    # Pad one day each side and filter afterward
    raw = await _fetch_points(d_from - timedelta(days=1), d_to + timedelta(days=1))

    utc_start, _ = local_date_to_utc_range(d_from, tz_name)
    _, utc_end = local_date_to_utc_range(d_to, tz_name)

    def in_range(p: dict) -> bool:
        dt = datetime.fromtimestamp(p["tst"], tz=ZoneInfo("UTC"))
        return utc_start <= dt < utc_end

    results = []
    for p in sorted(raw, key=lambda x: x["tst"]):
        if not in_range(p):
            continue
        dt_local = datetime.fromtimestamp(p["tst"], tz=ZoneInfo("UTC")).astimezone(tz)
        results.append({
            "time": dt_local.isoformat(timespec="seconds"),
            "lat": p.get("lat"),
            "lon": p.get("lon"),
            "activity": _activity_label(p.get("vel")),
        })

    return results
