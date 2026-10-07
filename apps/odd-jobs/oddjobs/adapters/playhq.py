"""PlayHQ adapter (grade cricket).

Uses the anonymous GraphQL endpoint the PlayHQ web app itself calls. This is not the
documented keyed REST API, so it may change without notice. Times are Sydney local
clock times with no timezone.
"""
from __future__ import annotations

import re
from datetime import date, time

import httpx

from oddjobs.core.errors import AdapterError
from oddjobs.models import Day, Fixture, Status

GRAPHQL_URL = "https://api.playhq.com/graphql"

QUERY = """
query($id: ID!) {
  discoverTeamFixture(teamID: $id) {
    name
    fixture {
      games {
        id
        status { value }
        home { ... on DiscoverTeam { name } ... on ProvisionalTeam { name } }
        away { ... on DiscoverTeam { name } ... on ProvisionalTeam { name } }
        allocation { dateTimeList { date time } court { venue { name suburb } } }
      }
    }
  }
}
"""

_TEAM_ID_RE = re.compile(r"^[A-Za-z0-9-]+$")


def _short(name: str) -> str:
    return re.sub(r"\s+(First Grade|1st)$", "", name)


def _status(value: str) -> Status:
    value = (value or "").upper()
    if "POSTPON" in value:
        return Status.POSTPONED
    if "ABANDON" in value or "CANCEL" in value:
        return Status.ABANDONED
    if value == "FINAL":
        return Status.COMPLETED
    return Status.SCHEDULED


def _venue(allocation: dict) -> str | None:
    court = allocation.get("court") or {}
    venue = court.get("venue") or {}
    name = venue.get("name")
    if not name:
        return None
    suburb = venue.get("suburb")  # PlayHQ returns these in capitals
    return f"{name}, {suburb.title()}" if suburb else name


def _days(allocation: dict) -> tuple[Day, ...]:
    days = []
    for entry in allocation.get("dateTimeList") or []:
        try:
            days.append(Day(date=date.fromisoformat(entry["date"]), start=time.fromisoformat(entry["time"])))
        except (KeyError, TypeError, ValueError):
            continue  # date or time not set yet; if the format itself changed, zero fixtures trips the job check
    return tuple(days)


def _parse_game(game: dict, *, round_name: str | None, team: str, url: str | None) -> Fixture | None:
    home = (game.get("home") or {}).get("name") or ""
    away = (game.get("away") or {}).get("name") or ""
    if team not in (home, away):
        return None
    allocation = game.get("allocation") or {}
    days = _days(allocation)
    if not days:
        return None  # not yet scheduled; nothing to put on a calendar
    return Fixture(
        source_id=str(game["id"]),
        title=f"{_short(home)} v {_short(away)}",
        days=days,
        status=_status((game.get("status") or {}).get("value", "")),
        venue=_venue(allocation),
        description=round_name,
        url=url,
    )


def parse_rounds(data: dict, *, team: str, url: str | None) -> list[Fixture]:
    rounds = (data.get("data") or {}).get("discoverTeamFixture")
    if rounds is None:
        raise AdapterError("playhq: response has no discoverTeamFixture (API changed?)")
    fixtures: dict[str, Fixture] = {}
    for rnd in rounds:
        for game in (rnd.get("fixture") or {}).get("games") or []:
            try:
                fixture = _parse_game(game, round_name=rnd.get("name"), team=team, url=url)
            except (KeyError, ValueError, TypeError, AttributeError):
                continue  # one malformed game must not cost the whole season
            if fixture:
                fixtures[fixture.source_id] = fixture
    return list(fixtures.values())


def fetch_fixtures(client: httpx.Client, *, team_id: str, team: str, url: str | None = None) -> list[Fixture]:
    if not _TEAM_ID_RE.match(team_id):
        raise AdapterError(f"playhq: bad team id {team_id!r}")
    try:
        response = client.post(
            GRAPHQL_URL,
            json={"query": QUERY, "variables": {"id": team_id}},
            headers={"tenant": "ca", "Origin": "https://www.playhq.com"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise AdapterError(f"playhq: request failed: {e}") from None
    if payload.get("errors"):
        raise AdapterError(f"playhq: GraphQL errors: {payload['errors'][:1]}")
    return parse_rounds(payload, team=team, url=url)
