"""cricket.com.au adapter.

Each series page (https://www.cricket.com.au/matches/series/CA:<id>) embeds the full
fixture list as `window.FIXTURES_DATA = JSON.parse('...')`. The slug after the id is
ignored by the site, so only the id is needed.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from oddjobs.core.errors import AdapterError
from oddjobs.models import Day, Fixture, Status

SERIES_URL = "https://www.cricket.com.au/matches/series/{series_id}"
_BLOB_RE = re.compile(r"FIXTURES_DATA\s*=\s*JSON\.parse\('(.*?)'\);", re.S)
_SERIES_ID_RE = re.compile(r"^CA:\d+$")
_JS_ESCAPE_RE = re.compile(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", re.S)
_JS_SIMPLE = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}


def _js_unescape(match: re.Match) -> str:
    token = match.group(1)
    if token[0] in "ux" and len(token) > 1:
        return chr(int(token[1:], 16))
    return _JS_SIMPLE.get(token, token)


def extract_fixtures_data(html: str) -> list[dict]:
    match = _BLOB_RE.search(html)
    if not match:
        raise AdapterError("cricket.com.au: FIXTURES_DATA blob not found (page layout changed?)")
    try:
        data = json.loads(_JS_ESCAPE_RE.sub(_js_unescape, match.group(1)))
    except json.JSONDecodeError as e:
        raise AdapterError(f"cricket.com.au: FIXTURES_DATA is not valid JSON: {e}") from None
    if not isinstance(data, list):
        raise AdapterError("cricket.com.au: FIXTURES_DATA is not a list")
    return data


def _strip_men(name: str) -> str:
    return re.sub(r"\s+Men$", "", name)


def _status(raw: dict) -> Status:
    text = f"{raw.get('gameStatusId', '')} {raw.get('gameStatus', '')}".lower()
    if "postpone" in text:
        return Status.POSTPONED
    if "abandon" in text:
        return Status.ABANDONED
    if raw.get("isCompleted"):
        return Status.COMPLETED
    return Status.SCHEDULED


def _team_name(raw: dict, side: str) -> str | None:
    return (raw.get(side) or {}).get("name")


def _title(raw: dict) -> str:
    name = raw.get("name") or "Match"
    if " v " in name:
        return name
    home = _strip_men(_team_name(raw, "homeTeam") or "TBC")
    away = _strip_men(_team_name(raw, "awayTeam") or "TBC")
    return f"{home} v {away}: {name}"


def _venue(raw: dict) -> str | None:
    venue = raw.get("venue") or {}
    name = venue.get("name")
    if not name:
        return None
    location = venue.get("location")
    return f"{name}, {location}" if location else name


def parse_fixtures(raw_fixtures: list[dict], *, team: str, tz: ZoneInfo, series_url: str) -> list[Fixture]:
    fixtures: dict[str, Fixture] = {}
    for raw in raw_fixtures:
        if team not in (_team_name(raw, "homeTeam"), _team_name(raw, "awayTeam")):
            continue
        if not raw.get("startDateTime"):
            continue  # not yet scheduled; nothing to put on a calendar
        start = datetime.fromisoformat(raw["startDateTime"].replace("Z", "+00:00")).astimezone(tz)
        day_count = max(1, int(raw.get("numberOfDays") or 1))
        days = tuple(
            Day(date=start.date() + timedelta(days=i), start=start.time()) for i in range(day_count)
        )
        source_id = str(raw["id"])
        fixtures[source_id] = Fixture(
            source_id=source_id,
            title=_title(raw),
            days=days,
            status=_status(raw),
            venue=_venue(raw),
            description=(raw.get("competition") or {}).get("name"),
            url=series_url,
        )
    return list(fixtures.values())


def fetch_fixtures(
    client: httpx.Client, *, series: tuple[str, ...], team: str, tz: ZoneInfo
) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for series_id in series:
        if not _SERIES_ID_RE.match(series_id):
            raise AdapterError(f"cricket.com.au: bad series id {series_id!r} (expected CA:<digits>)")
        url = SERIES_URL.format(series_id=series_id)
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise AdapterError(f"cricket.com.au: fetching {url} failed: {e}") from None
        fixtures.extend(
            parse_fixtures(extract_fixtures_data(response.text), team=team, tz=tz, series_url=url)
        )
    return fixtures
