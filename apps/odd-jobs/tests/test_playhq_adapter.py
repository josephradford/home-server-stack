import json
from datetime import date, time

import httpx
import pytest

from oddjobs.adapters import playhq
from oddjobs.core.errors import AdapterError
from oddjobs.models import Status
from tests.helpers import playhq_game, playhq_response

ME = "Parramatta First Grade"

RESPONSE = playhq_response(
    [
        ("Round 1", []),
        ("Round 2", [
            playhq_game("g2", "UTS North Sydney 1st", ME, [("2026-10-03", "09:30:00")],
                        status="FINAL", venue="Bon Andrews Park", suburb=None),
            playhq_game("x1", "Bankstown 1st", "Gordon 1st", [("2026-10-03", "10:00:00")]),
        ]),
        ("Round 4", [
            playhq_game("g4", ME, "Fairfield-Liverpool 1st",
                        [("2026-10-17", "10:00:00"), ("2026-10-24", "10:00:00")]),
        ]),
        ("Round 9", [playhq_game("g9", ME, "Randwick Petersham 1st", [])]),
    ]
)


def test_filters_to_team_and_builds_fixtures():
    fixtures = playhq.parse_rounds(RESPONSE, team=ME, url="https://team.page")
    assert [f.source_id for f in fixtures] == ["g2", "g4"]  # x1 is another match; g9 has no dates
    played, two_day = fixtures
    assert played.title == "UTS North Sydney v Parramatta"
    assert played.status is Status.COMPLETED
    assert played.venue == "Bon Andrews Park"
    assert played.description == "Round 2"
    assert played.days[0].start == time(9, 30)
    assert two_day.title == "Parramatta v Fairfield-Liverpool"
    assert two_day.venue == "Old Kings Oval, North Parramatta"
    assert [d.date for d in two_day.days] == [date(2026, 10, 17), date(2026, 10, 24)]
    assert two_day.url == "https://team.page"


def test_status_mapping():
    assert playhq._status("POSTPONED") is Status.POSTPONED
    assert playhq._status("ABANDONED") is Status.ABANDONED
    assert playhq._status("CANCELLED") is Status.ABANDONED
    assert playhq._status("UPCOMING") is Status.SCHEDULED
    assert playhq._status("") is Status.SCHEDULED


def test_missing_data_raises():
    with pytest.raises(AdapterError, match="API changed"):
        playhq.parse_rounds({"data": {"discoverTeamFixture": None}}, team=ME, url=None)


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_posts_graphql_with_tenant_header():
    captured = {}

    def handler(request):
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=RESPONSE)

    with client_for(handler) as client:
        fixtures = playhq.fetch_fixtures(client, team_id="bb481fee", team=ME)
    assert captured["headers"]["tenant"] == "ca"
    assert captured["body"]["variables"] == {"id": "bb481fee"}
    assert len(fixtures) == 2


def test_fetch_surfaces_graphql_errors_and_http_errors():
    with client_for(lambda r: httpx.Response(200, json={"errors": [{"message": "nope"}]})) as client:
        with pytest.raises(AdapterError, match="GraphQL errors"):
            playhq.fetch_fixtures(client, team_id="bb481fee", team=ME)
    with client_for(lambda r: httpx.Response(403)) as client:
        with pytest.raises(AdapterError, match="request failed"):
            playhq.fetch_fixtures(client, team_id="bb481fee", team=ME)
    with client_for(lambda r: httpx.Response(200, text="<html>blocked</html>")) as client:
        with pytest.raises(AdapterError, match="request failed"):
            playhq.fetch_fixtures(client, team_id="bb481fee", team=ME)


def test_rejects_bad_team_id():
    with client_for(lambda r: pytest.fail("no request expected")) as client:
        with pytest.raises(AdapterError, match="bad team id"):
            playhq.fetch_fixtures(client, team_id="x; drop", team=ME)


def test_unset_times_and_provisional_teams_do_not_break_parsing():
    response = playhq_response(
        [
            ("Round 5", [
                playhq_game("a", ME, "Gordon 1st", [("2026-10-31", "10:00:00")]),
                playhq_game("b", ME, "Mosman 1st", [("2026-11-07", None), ("2026-11-08", "10:00:00")]),
                playhq_game("c", ME, "Penrith 1st", [(None, None)]),
            ]),
            ("Finals", [{"id": "f", "status": {"value": "UPCOMING"}, "home": {"name": None},
                         "away": None, "allocation": None}]),
        ]
    )
    fixtures = playhq.parse_rounds(response, team=ME, url=None)
    assert [f.source_id for f in fixtures] == ["a", "b"]
    assert [d.date.day for d in fixtures[1].days] == [8]  # the entry without a time is dropped
