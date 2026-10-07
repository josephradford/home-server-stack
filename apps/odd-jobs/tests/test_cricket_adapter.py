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
    assert len(fixtures) == 4  # same fixture ids across series pages are kept per page


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
