"""cricket.com.au adapter.

Each series page (https://www.cricket.com.au/matches/series/CA:<id>) embeds the full
fixture list as `window.FIXTURES_DATA = JSON.parse('...')`. The slug after the id is
ignored by the site, so only the id is needed.

New tours get new series ids, so a calendar can set `discover: true` with the site's numeric
`team_id`: the competitions API the site's own series listing uses
(https://apiv2.cricket.com.au/web/competitions/format/year) is asked for the team's series in
this year and next, and each is fetched and filtered by team. The HTML series index can't be
used for this: it omits some series (e.g. Australia v England T20Is) and only shows one year.
Pinned `series` ids remain for anything the API doesn't return.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from oddjobs.core.errors import AdapterError
from oddjobs.models import Day, Fixture, Status

log = logging.getLogger("oddjobs.cricket")

SERIES_URL = "https://www.cricket.com.au/matches/series/{series_id}"
COMPETITIONS_URL = "https://apiv2.cricket.com.au/web/competitions/format/year"
COMPETITIONS_LIMIT = 25  # the API rejects larger values; a team has far fewer series per year
THROTTLE_SECONDS = 1.5  # between discovered-series fetches; the site 429s a fast scan
RETRY_429_SECONDS = 10.0
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


def _parse_one(
    raw: dict, *, team: str, tz: ZoneInfo, series_url: str, game_types: tuple[str, ...] = ()
) -> Fixture | None:
    if team not in (_team_name(raw, "homeTeam"), _team_name(raw, "awayTeam")):
        return None
    if game_types and raw.get("gameType") not in game_types:
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


def parse_fixtures(
    raw_fixtures: list[dict],
    *,
    team: str,
    tz: ZoneInfo,
    series_url: str,
    game_types: tuple[str, ...] = (),
) -> list[Fixture]:
    fixtures: dict[str, Fixture] = {}
    for raw in raw_fixtures:
        try:
            fixture = _parse_one(raw, team=team, tz=tz, series_url=series_url, game_types=game_types)
        except (KeyError, ValueError, TypeError):
            continue  # one malformed record must not cost the whole calendar; if the format itself changed, zero fixtures trips the job check
        if fixture:
            fixtures[fixture.source_id] = fixture
    return list(fixtures.values())


def _get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    response = client.get(url, params=params)
    if response.status_code == 429:  # rate limited: back off once, then let it fail
        time.sleep(RETRY_429_SECONDS)
        response = client.get(url, params=params)
    response.raise_for_status()
    return response


def discover_series(client: httpx.Client, team_id: int, years: tuple[int, ...]) -> list[str]:
    """Series ids (CA:<id>) the site lists for this team in the given years, upcoming and in progress."""
    ids: dict[str, None] = {}
    for year in years:
        try:
            response = _get(
                client,
                COMPETITIONS_URL,
                params={
                    "year": year,
                    "teamId": team_id,
                    "isCompleted": "false",
                    "limit": COMPETITIONS_LIMIT,
                    "jsconfig": "eccn:true",
                    "format": "json",
                },
            )
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise AdapterError(f"cricket.com.au: fetching competitions for {year} failed: {e}") from None
        if not isinstance(data, dict) or data.get("responseError"):
            raise AdapterError(f"cricket.com.au: competitions API error for {year}: {data!r:.200}")
        for competition in data.get("competitionDetails") or []:
            if isinstance(competition, dict) and isinstance(competition.get("competitionId"), int):
                ids[f"CA:{competition['competitionId']}"] = None
    return list(ids)


def _fetch_series(
    client: httpx.Client, series_id: str, *, team: str, tz: ZoneInfo, game_types: tuple[str, ...]
) -> list[Fixture]:
    url = SERIES_URL.format(series_id=series_id)
    try:
        response = _get(client, url)
    except httpx.HTTPError as e:
        raise AdapterError(f"cricket.com.au: fetching {url} failed: {e}") from None
    return parse_fixtures(
        extract_fixtures_data(response.text), team=team, tz=tz, series_url=url, game_types=game_types
    )


def fetch_fixtures(
    client: httpx.Client,
    *,
    series: tuple[str, ...],
    team: str,
    tz: ZoneInfo,
    discover: bool = False,
    team_id: int | None = None,
    years: tuple[int, ...] | None = None,
    game_types: tuple[str, ...] = (),
) -> list[Fixture]:
    for series_id in series:
        if not _SERIES_ID_RE.match(series_id):
            raise AdapterError(f"cricket.com.au: bad series id {series_id!r} (expected CA:<digits>)")
    fixtures: dict[str, Fixture] = {}
    for series_id in series:  # pinned: a failure here fails the calendar
        for fixture in _fetch_series(client, series_id, team=team, tz=tz, game_types=game_types):
            fixtures[fixture.source_id] = fixture
    if discover:
        if team_id is None:
            raise AdapterError("cricket.com.au: discover needs a team_id")
        if years is None:
            this_year = datetime.now(tz).year
            years = (this_year, this_year + 1)
        for series_id in discover_series(client, team_id, years):
            if series_id in series:
                continue
            time.sleep(THROTTLE_SECONDS)
            try:  # discovered: one unrelated series misbehaving must not cost the calendar
                found = _fetch_series(client, series_id, team=team, tz=tz, game_types=game_types)
            except AdapterError as e:
                log.warning("skipping discovered series %s: %s", series_id, e)
                continue
            if found:
                log.info("discovered series %s has %d fixtures for %s", series_id, len(found), team)
            for fixture in found:
                fixtures.setdefault(fixture.source_id, fixture)
    return list(fixtures.values())
