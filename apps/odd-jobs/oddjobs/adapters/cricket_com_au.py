"""cricket.com.au adapter.

Each series page (https://www.cricket.com.au/matches/series/CA:<id>) embeds the full
fixture list as `window.FIXTURES_DATA = JSON.parse('...')`. The slug after the id is
ignored by the site, so only the id is needed.

New tours get new series ids, so a calendar can set `discover: true`: the /matches page
links every current series, and each one is fetched and filtered by team. Pinned `series`
ids are still needed for competitions that page doesn't link (e.g. the Sheffield Shield).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from oddjobs.core.errors import AdapterError
from oddjobs.models import Day, Fixture, Status

log = logging.getLogger("oddjobs.cricket")

SERIES_URL = "https://www.cricket.com.au/matches/series/{series_id}"
MATCHES_URL = "https://www.cricket.com.au/matches"
_SERIES_LINK_RE = re.compile(r"/matches/series/(CA:\d+)")
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


def _parse_one(raw: dict, *, team: str, tz: ZoneInfo, series_url: str) -> Fixture | None:
    if team not in (_team_name(raw, "homeTeam"), _team_name(raw, "awayTeam")):
        return None
    if not raw.get("startDateTime"):
        return None  # not yet scheduled; nothing to put on a calendar
    start = datetime.fromisoformat(raw["startDateTime"].replace("Z", "+00:00")).astimezone(tz)
    day_count = max(1, int(raw.get("numberOfDays") or 1))
    days = tuple(Day(date=start.date() + timedelta(days=i), start=start.time()) for i in range(day_count))
    return Fixture(
        source_id=str(raw["id"]),
        title=_title(raw),
        days=days,
        status=_status(raw),
        venue=_venue(raw),
        description=(raw.get("competition") or {}).get("name"),
        url=series_url,
    )


def parse_fixtures(raw_fixtures: list[dict], *, team: str, tz: ZoneInfo, series_url: str) -> list[Fixture]:
    fixtures: dict[str, Fixture] = {}
    for raw in raw_fixtures:
        try:
            fixture = _parse_one(raw, team=team, tz=tz, series_url=series_url)
        except (KeyError, ValueError, TypeError):
            continue  # one malformed record must not cost the whole calendar; if the format itself changed, zero fixtures trips the job check
        if fixture:
            fixtures[fixture.source_id] = fixture
    return list(fixtures.values())


def discover_series(client: httpx.Client) -> list[str]:
    """Series ids linked from the /matches page, in page order."""
    try:
        response = client.get(MATCHES_URL)
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise AdapterError(f"cricket.com.au: fetching {MATCHES_URL} failed: {e}") from None
    ids = list(dict.fromkeys(_SERIES_LINK_RE.findall(response.text)))
    if not ids:
        raise AdapterError("cricket.com.au: no series links found on /matches (page layout changed?)")
    return ids


def _fetch_series(client: httpx.Client, series_id: str, *, team: str, tz: ZoneInfo) -> list[Fixture]:
    url = SERIES_URL.format(series_id=series_id)
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise AdapterError(f"cricket.com.au: fetching {url} failed: {e}") from None
    return parse_fixtures(extract_fixtures_data(response.text), team=team, tz=tz, series_url=url)


def fetch_fixtures(
    client: httpx.Client,
    *,
    series: tuple[str, ...],
    team: str,
    tz: ZoneInfo,
    discover: bool = False,
) -> list[Fixture]:
    for series_id in series:
        if not _SERIES_ID_RE.match(series_id):
            raise AdapterError(f"cricket.com.au: bad series id {series_id!r} (expected CA:<digits>)")
    fixtures: dict[str, Fixture] = {}
    for series_id in series:  # pinned: a failure here fails the calendar
        for fixture in _fetch_series(client, series_id, team=team, tz=tz):
            fixtures[fixture.source_id] = fixture
    if discover:
        for series_id in discover_series(client):
            if series_id in series:
                continue
            try:  # discovered: one unrelated series misbehaving must not cost the calendar
                found = _fetch_series(client, series_id, team=team, tz=tz)
            except AdapterError as e:
                log.warning("skipping discovered series %s: %s", series_id, e)
                continue
            if found:
                log.info("discovered series %s has %d fixtures for %s", series_id, len(found), team)
            for fixture in found:
                fixtures.setdefault(fixture.source_id, fixture)
    return list(fixtures.values())
