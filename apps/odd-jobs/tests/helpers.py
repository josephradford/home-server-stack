"""Builders for realistic source responses, used by adapter and job tests."""
import json


def series_html(fixtures: list[dict]) -> str:
    """Wrap fixtures the way cricket.com.au embeds them: JSON inside a JS single-quoted string."""
    js = json.dumps(fixtures, separators=(",", ":")).replace("\\", "\\\\").replace("'", "\\'")
    return (
        "<html><body><section>"
        f"<script>window.FIXTURES_DATA = JSON.parse('{js}');</script>"
        "</section></body></html>"
    )


def ca_fixture(
    id: int,
    name: str,
    start: str,
    days: int,
    home: str,
    away: str,
    venue: str = "Perth Stadium",
    location: str = "Perth",
    **extra,
) -> dict:
    return {
        "id": id,
        "name": name,
        "startDateTime": start,
        "endDateTime": start,
        "numberOfDays": days,
        "isCompleted": False,
        "gameStatusId": "Scheduled",
        "gameStatus": "Scheduled",
        "competition": {"id": 1, "name": "Test Series"},
        "venue": {"id": 1, "name": venue, "location": location},
        "homeTeam": {"id": 1, "name": home},
        "awayTeam": {"id": 2, "name": away},
        **extra,
    }


def playhq_game(
    id: str,
    home: str,
    away: str,
    times: list[tuple[str, str]],
    status: str = "UPCOMING",
    venue: str | None = "Old Kings Oval",
    suburb: str | None = "NORTH PARRAMATTA",
) -> dict:
    allocation = None
    if times:
        allocation = {
            "dateTimeList": [{"date": d, "time": t} for d, t in times],
            "court": {"venue": {"name": venue, "suburb": suburb}} if venue else None,
        }
    return {
        "id": id,
        "status": {"value": status},
        "home": {"name": home},
        "away": {"name": away},
        "allocation": allocation,
    }


def playhq_response(rounds: list[tuple[str, list[dict]]]) -> dict:
    return {
        "data": {
            "discoverTeamFixture": [
                {"name": name, "fixture": {"games": games}} for name, games in rounds
            ]
        }
    }
