from datetime import date, time
from zoneinfo import ZoneInfo

import httpx
import pytest

from oddjobs.adapters import cricket_com_au as ca
from oddjobs.core.errors import AdapterError
from oddjobs.models import Status
from tests.helpers import ca_fixture, series_html

SYDNEY = ZoneInfo("Australia/Sydney")

TESTS = [
    ca_fixture(1, "1st Test", "2026-12-09T02:20:00Z", 5, "Australia Men", "New Zealand Men"),
    ca_fixture(2, "2nd Test", "2026-12-17T00:30:00Z", 5, "Australia Men", "New Zealand Men",
               venue="Adelaide Oval", location="Adelaide"),
    ca_fixture(3, "Only Test", "2026-12-20T00:00:00Z", 5, "Afghanistan Men", "Bangladesh Men"),
]


def test_extract_handles_js_escaping():
    # Apostrophes arrive as \' and unicode escapes as \\u0027 (JS string layer, then JSON layer).
    fixtures = [ca_fixture(9, "1st Test", "2026-12-09T02:20:00Z", 5, "Australia Men", "NZ Men",
                           venue="St George's Park")]
    html = series_html(fixtures).replace("St George\\'s Park", "St George\\\\u0027s Park")
    assert ca.extract_fixtures_data(html)[0]["venue"]["name"] == "St George's Park"


def test_extract_raises_when_blob_missing():
    with pytest.raises(AdapterError, match="FIXTURES_DATA"):
        ca.extract_fixtures_data("<html>redesigned</html>")


def test_extract_raises_on_garbage_json():
    with pytest.raises(AdapterError, match="valid JSON"):
        ca.extract_fixtures_data("window.FIXTURES_DATA = JSON.parse('{nope');")


def test_parse_filters_to_team_and_expands_days_in_sydney_time():
    fixtures = ca.parse_fixtures(TESTS, team="Australia Men", tz=SYDNEY, series_url="https://s")
    assert [f.source_id for f in fixtures] == ["1", "2"]
    first = fixtures[0]
    assert first.title == "Australia v New Zealand: 1st Test"
    assert first.venue == "Perth Stadium, Perth"
    assert first.url == "https://s"
    assert first.description == "Test Series"
    # 02:20Z on 9 Dec 2026 is 13:20 AEDT; five consecutive days from there.
    assert first.days[0].date == date(2026, 12, 9) and first.days[0].start == time(13, 20)
    assert [d.date.day for d in first.days] == [9, 10, 11, 12, 13]


def test_sydney_date_can_differ_from_utc_date():
    shield = ca_fixture(4, "New South Wales v Tasmanian Tigers", "2026-10-07T23:30:00Z", 4,
                        "NSW Men", "Tasmanian Tigers Men")
    (fixture,) = ca.parse_fixtures([shield], team="NSW Men", tz=SYDNEY, series_url="https://s")
    assert fixture.title == "New South Wales v Tasmanian Tigers"
    assert fixture.days[0].date == date(2026, 10, 8) and fixture.days[0].start == time(10, 30)
    assert len(fixture.days) == 4


def test_status_mapping_and_day_count_floor():
    postponed = ca_fixture(5, "3rd Test", "2026-12-25T23:30:00Z", 0, "Australia Men", "NZ Men",
                           gameStatusId="Postponed", gameStatus="Postponed")
    done = ca_fixture(6, "4th Test", "2027-01-03T23:30:00Z", 5, "Australia Men", "NZ Men",
                      isCompleted=True)
    a, b = ca.parse_fixtures([postponed, done], team="Australia Men", tz=SYDNEY, series_url="https://s")
    assert a.status is Status.POSTPONED and len(a.days) == 1
    assert b.status is Status.COMPLETED


def test_duplicate_ids_are_collapsed():
    dup = [TESTS[0], TESTS[0]]
    assert len(ca.parse_fixtures(dup, team="Australia Men", tz=SYDNEY, series_url="https://s")) == 1


@pytest.fixture(autouse=True)
def no_throttle(monkeypatch):
    monkeypatch.setattr(ca, "THROTTLE_SECONDS", 0)
    monkeypatch.setattr(ca, "RETRY_429_SECONDS", 0)


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_requests_each_series_page():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=series_html(TESTS))

    with client_for(handler) as client:
        fixtures = ca.fetch_fixtures(client, series=("CA:4605", "CA:4689"), team="Australia Men", tz=SYDNEY)
    assert seen == [
        "https://www.cricket.com.au/matches/series/CA:4605",
        "https://www.cricket.com.au/matches/series/CA:4689",
    ]
    assert len(fixtures) == 2  # the same fixture id seen in two series is one fixture


def test_fetch_wraps_http_errors():
    with client_for(lambda r: httpx.Response(503)) as client:
        with pytest.raises(AdapterError, match="failed"):
            ca.fetch_fixtures(client, series=("CA:4605",), team="Australia Men", tz=SYDNEY)


def test_fetch_rejects_bad_series_id_without_a_request():
    def handler(request):
        raise AssertionError("no request expected")

    with client_for(handler) as client:
        with pytest.raises(AdapterError, match="bad series id"):
            ca.fetch_fixtures(client, series=("CA:4605/../../x",), team="Australia Men", tz=SYDNEY)


def test_tbc_teams_and_unscheduled_fixtures_do_not_break_parsing():
    final = ca_fixture(7, "Final", "2027-03-25T23:30:00Z", 5, "NSW Men", "x")
    final["awayTeam"] = None  # opponent not decided yet
    unscheduled = ca_fixture(8, "Semi", "2027-03-01T00:00:00Z", 5, "NSW Men", "Vic Men")
    del unscheduled["startDateTime"]
    unrelated = ca_fixture(9, "Final", "2027-03-25T23:30:00Z", 5, "x", "y")
    unrelated["homeTeam"] = None
    fixtures = ca.parse_fixtures([final, unscheduled, unrelated], team="NSW Men", tz=SYDNEY, series_url="https://s")
    assert [f.title for f in fixtures] == ["NSW v TBC: Final"]


def test_one_malformed_fixture_is_skipped_without_losing_the_rest():
    good = ca_fixture(1, "1st Test", "2026-12-09T02:20:00Z", 5, "Australia Men", "New Zealand Men")
    bad_date = ca_fixture(2, "2nd Test", "not-a-date", 5, "Australia Men", "New Zealand Men")
    no_id = ca_fixture(3, "3rd Test", "2026-12-25T23:30:00Z", 5, "Australia Men", "New Zealand Men")
    del no_id["id"]
    bad_days = ca_fixture(4, "4th Test", "2027-01-03T23:30:00Z", "five", "Australia Men", "New Zealand Men")
    fixtures = ca.parse_fixtures([bad_date, good, no_id, bad_days], team="Australia Men", tz=SYDNEY, series_url="https://s")
    assert [f.source_id for f in fixtures] == ["1"]


SA_TEST = ca_fixture(20, "1st Test", "2026-10-09T07:30:00Z", 5, "South Africa Men", "Australia Men")
INDIA_TEST = ca_fixture(30, "1st Test", "2027-01-21T04:00:00Z", 5, "India Men", "Australia Men")
COMPETITIONS_PATH = "/web/competitions/format/year"


def competitions(*ids):
    return {"competitionDetails": [{"competitionId": i, "name": f"series {i}"} for i in ids], "responseError": False}


def discovery_handler(by_year, pages):
    """by_year: {year: competitions payload}; pages: {series path: html}. Records every request."""
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == COMPETITIONS_PATH:
            payload = by_year.get(int(request.url.params["year"]))
            return httpx.Response(200, json=payload) if payload is not None else httpx.Response(503)
        body = pages.get(request.url.path)
        return httpx.Response(200, text=body) if body is not None else httpx.Response(503)

    return handler, seen


def test_discover_series_asks_the_api_per_year_for_the_team_and_dedupes():
    handler, seen = discovery_handler({2026: competitions(4568, 4605), 2027: competitions(4605, 4617, 4698)}, {})
    with client_for(handler) as client:
        ids = ca.discover_series(client, 23, (2026, 2027))
    assert ids == ["CA:4568", "CA:4605", "CA:4617", "CA:4698"]
    params = [dict(r.url.params) for r in seen]
    assert [p["year"] for p in params] == ["2026", "2027"]
    assert all(p["teamId"] == "23" and p["isCompleted"] == "false" and p["limit"] == "25" for p in params)


def test_discover_raises_on_api_error_payloads_and_http_failures():
    bad = {"competitionDetails": [], "responseError": True, "responseStatus": {"message": "nope"}}
    handler, _ = discovery_handler({2026: bad}, {})
    with client_for(handler) as client:
        with pytest.raises(AdapterError, match="API error"):
            ca.discover_series(client, 23, (2026,))
        with pytest.raises(AdapterError, match="failed"):
            ca.discover_series(client, 23, (2030,))  # handler answers 503


def test_fetch_with_discover_adds_new_series_and_dedupes_pinned():
    handler, seen = discovery_handler(
        {2026: competitions(4568, 4605), 2027: competitions(4617)},
        {
            "/matches/series/CA:4605": series_html(TESTS),
            "/matches/series/CA:4568": series_html([SA_TEST]),
            "/matches/series/CA:4617": series_html([INDIA_TEST]),
        },
    )
    with client_for(handler) as client:
        fixtures = ca.fetch_fixtures(
            client, series=("CA:4605",), team="Australia Men", tz=SYDNEY,
            discover=True, team_id=23, years=(2026, 2027),
        )
    assert sorted(f.source_id for f in fixtures) == ["1", "2", "20", "30"]
    assert [r.url.path for r in seen].count("/matches/series/CA:4605") == 1  # pinned series is not fetched twice


def test_discovered_series_failure_is_skipped_but_pinned_failure_is_not():
    handler, _ = discovery_handler(
        {2026: competitions(4568, 4605)},
        {"/matches/series/CA:4605": series_html(TESTS)},  # CA:4568 returns 503
    )
    with client_for(handler) as client:
        fixtures = ca.fetch_fixtures(
            client, series=(), team="Australia Men", tz=SYDNEY, discover=True, team_id=23, years=(2026,)
        )
        assert [f.source_id for f in fixtures] == ["1", "2"]
        with pytest.raises(AdapterError, match="failed"):
            ca.fetch_fixtures(client, series=("CA:4568",), team="Australia Men", tz=SYDNEY)


def test_discover_requires_a_team_id():
    with client_for(lambda r: httpx.Response(200)) as client:
        with pytest.raises(AdapterError, match="team_id"):
            ca.fetch_fixtures(client, series=(), team="Australia Men", tz=SYDNEY, discover=True)


def test_default_years_are_this_year_and_next(monkeypatch):
    seen_years = []

    def handler(request):
        if request.url.path == COMPETITIONS_PATH:
            seen_years.append(int(request.url.params["year"]))
            return httpx.Response(200, json=competitions())
        return httpx.Response(503)

    with client_for(handler) as client:
        ca.fetch_fixtures(client, series=(), team="Australia Men", tz=SYDNEY, discover=True, team_id=23)
    from datetime import datetime
    year = datetime.now(SYDNEY).year
    assert seen_years == [year, year + 1]


def test_fetch_retries_once_after_429():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429)
        return httpx.Response(200, text=series_html(TESTS))

    with client_for(handler) as client:
        fixtures = ca.fetch_fixtures(client, series=("CA:4605",), team="Australia Men", tz=SYDNEY)
    assert len(fixtures) == 2 and len(calls) == 2


def test_game_types_filter_keeps_only_listed_formats():
    test = ca_fixture(1, "1st Test", "2026-12-09T02:20:00Z", 5, "Australia Men", "India Men", gameType="Test")
    odi = ca_fixture(2, "1st ODI", "2026-11-13T03:00:00Z", 1, "Australia Men", "England Men", gameType="One Day International")
    kept = ca.parse_fixtures([test, odi], team="Australia Men", tz=SYDNEY, series_url="https://s", game_types=("Test",))
    assert [f.source_id for f in kept] == ["1"]
    assert len(ca.parse_fixtures([test, odi], team="Australia Men", tz=SYDNEY, series_url="https://s")) == 2
