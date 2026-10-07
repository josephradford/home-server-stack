import httpx
import pytest
from icalendar import Calendar

from oddjobs.core.errors import ConfigError, OddJobsError
from oddjobs.jobs import JobContext
from oddjobs.jobs.calendars import CalendarsJob
from tests.helpers import ca_fixture, playhq_game, playhq_response, series_html

CONFIG = """
timezone: Australia/Sydney
calendars:
  - name: australia-tests
    title: Australia Men's Tests
    source: cricket_com_au
    series: ["CA:4605"]
    team: "Australia Men"
  - name: parramatta-first-grade
    title: Parramatta First Grade
    source: playhq
    team_id: bb481fee
    team: "Parramatta First Grade"
    duration_hours: 7
"""

TESTS_HTML = series_html(
    [ca_fixture(1, "1st Test", "2026-12-09T02:20:00Z", 5, "Australia Men", "New Zealand Men")]
)
PLAYHQ_JSON = playhq_response(
    [("Round 3", [playhq_game("g3", "Parramatta First Grade", "Northern District 1st",
                              [("2026-10-10", "10:00:00")])])]
)


def make_ctx(tmp_path, handler):
    config = tmp_path / "calendars.yaml"
    config.write_text(CONFIG)
    return JobContext(
        config_path=config,
        out_dir=tmp_path / "out",
        uid_domain="jobs.example.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def healthy(request):
    if "cricket.com.au" in str(request.url):
        return httpx.Response(200, text=TESTS_HTML)
    return httpx.Response(200, json=PLAYHQ_JSON)


def events(path):
    return list(Calendar.from_ical(path.read_bytes()).walk("VEVENT"))


def test_writes_one_ics_per_calendar(tmp_path):
    ctx = make_ctx(tmp_path, healthy)
    result = CalendarsJob().run(ctx)
    assert "australia-tests: 1 fixtures" in result.detail
    assert len(events(ctx.out_dir / "australia-tests.ics")) == 5  # 5-day Test
    (grade,) = events(ctx.out_dir / "parramatta-first-grade.ics")
    assert str(grade["summary"]) == "Parramatta v Northern District"
    assert grade["dtend"].dt - grade["dtstart"].dt == __import__("datetime").timedelta(hours=7)


def test_zero_fixtures_keeps_previous_calendar_and_fails(tmp_path):
    ctx = make_ctx(tmp_path, healthy)
    CalendarsJob().run(ctx)
    before = (ctx.out_dir / "australia-tests.ics").read_bytes()

    def broken(request):
        if "cricket.com.au" in str(request.url):
            return httpx.Response(200, text=series_html([]))
        return healthy(request)

    ctx2 = JobContext(ctx.config_path, ctx.out_dir, ctx.uid_domain,
                      httpx.Client(transport=httpx.MockTransport(broken)))
    with pytest.raises(OddJobsError, match="zero fixtures"):
        CalendarsJob().run(ctx2)
    assert (ctx.out_dir / "australia-tests.ics").read_bytes() == before


def test_one_failing_calendar_does_not_block_the_other(tmp_path):
    def only_playhq_ok(request):
        if "cricket.com.au" in str(request.url):
            return httpx.Response(500)
        return healthy(request)

    ctx = make_ctx(tmp_path, only_playhq_ok)
    with pytest.raises(OddJobsError, match="australia-tests"):
        CalendarsJob().run(ctx)
    assert (ctx.out_dir / "parramatta-first-grade.ics").exists()
    assert not (ctx.out_dir / "australia-tests.ics").exists()


def test_first_run_with_no_fixtures_writes_empty_calendar(tmp_path):
    def empty(request):
        if "cricket.com.au" in str(request.url):
            return httpx.Response(200, text=series_html([]))
        return healthy(request)

    ctx = make_ctx(tmp_path, empty)
    CalendarsJob().run(ctx)
    assert events(ctx.out_dir / "australia-tests.ics") == []


def test_missing_config_raises_config_error(tmp_path):
    ctx = JobContext(tmp_path / "missing.yaml", tmp_path / "out", "d",
                     httpx.Client(transport=httpx.MockTransport(healthy)))
    with pytest.raises(ConfigError):
        CalendarsJob().run(ctx)


def test_unexpected_exception_in_one_calendar_does_not_block_the_other(tmp_path, monkeypatch):
    from oddjobs.adapters import cricket_com_au

    def explode(*args, **kwargs):
        raise KeyError("homeTeam")

    monkeypatch.setattr(cricket_com_au, "fetch_fixtures", explode)
    ctx = make_ctx(tmp_path, healthy)
    with pytest.raises(OddJobsError, match="australia-tests"):
        CalendarsJob().run(ctx)
    assert (ctx.out_dir / "parramatta-first-grade.ics").exists()
