from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar

from oddjobs.ics_builder import build_calendar
from oddjobs.models import Day, Fixture, Status

SYDNEY = ZoneInfo("Australia/Sydney")
NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


def build(fixtures, duration=timedelta(hours=6)):
    data = build_calendar(
        calendar_name="cal",
        title="My Calendar",
        fixtures=fixtures,
        tz=SYDNEY,
        duration=duration,
        uid_domain="jobs.example.com",
        now=NOW,
    )
    return data, list(Calendar.from_ical(data).walk("VEVENT"))


def fixture(**kw):
    defaults = dict(
        source_id="100",
        title="A v B",
        days=(Day(date(2026, 12, 9), time(13, 20)),),
    )
    return Fixture(**{**defaults, **kw})


def test_one_event_per_day_with_day_suffix_and_stable_uids():
    days = tuple(Day(date(2026, 12, 9 + i), time(13, 20)) for i in range(5))
    _, events = build([fixture(title="Australia v New Zealand: 1st Test", days=days)])
    assert [str(e["summary"]) for e in events] == [
        f"Australia v New Zealand: 1st Test, Day {n}" for n in range(1, 6)
    ]
    assert [str(e["uid"]) for e in events] == [f"cal-100-d{n}@jobs.example.com" for n in range(1, 6)]


def test_single_day_has_no_suffix():
    _, events = build([fixture()])
    assert str(events[0]["summary"]) == "A v B"


def test_non_consecutive_days_keep_their_dates():
    days = (Day(date(2026, 10, 17), time(10, 0)), Day(date(2026, 10, 24), time(10, 0)))
    _, events = build([fixture(days=days)])
    starts = [e["dtstart"].dt.astimezone(SYDNEY).date() for e in events]
    assert starts == [date(2026, 10, 17), date(2026, 10, 24)]


def test_times_are_converted_to_utc_using_sydney_dst():
    # 10 Oct 2026 is AEDT (UTC+11); 10 Jul 2026 would be AEST (UTC+10).
    _, summer = build([fixture(days=(Day(date(2026, 10, 10), time(10, 0)),))])
    _, winter = build([fixture(days=(Day(date(2026, 7, 10), time(10, 0)),))])
    assert summer[0]["dtstart"].dt == datetime(2026, 10, 9, 23, 0, tzinfo=timezone.utc)
    assert winter[0]["dtstart"].dt == datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc)


def test_duration_sets_dtend():
    _, events = build([fixture()], duration=timedelta(hours=7))
    assert events[0]["dtend"].dt - events[0]["dtstart"].dt == timedelta(hours=7)


def test_status_prefixes():
    _, postponed = build([fixture(status=Status.POSTPONED)])
    _, abandoned = build([fixture(status=Status.ABANDONED)])
    _, completed = build([fixture(status=Status.COMPLETED)])
    assert str(postponed[0]["summary"]) == "[Postponed] A v B"
    assert str(abandoned[0]["summary"]) == "[Abandoned] A v B"
    assert str(completed[0]["summary"]) == "A v B"


def test_optional_fields_and_calendar_properties():
    data, events = build([fixture(venue="Old Kings Oval, North Parramatta", description="Round 3", url="https://x.test/m")])
    assert str(events[0]["location"]) == "Old Kings Oval, North Parramatta"
    assert str(events[0]["description"]) == "Round 3"
    assert str(events[0]["url"]) == "https://x.test/m"
    cal = Calendar.from_ical(data)
    assert str(cal["x-wr-calname"]) == "My Calendar"
    assert b"REFRESH-INTERVAL;VALUE=DURATION:P1D" in data


def test_events_are_ordered_by_first_day():
    later = fixture(source_id="2", days=(Day(date(2027, 1, 1), time(10, 0)),))
    earlier = fixture(source_id="1", days=(Day(date(2026, 12, 1), time(10, 0)),))
    _, events = build([later, earlier])
    assert [str(e["uid"]).split("-")[1] for e in events] == ["1", "2"]


def test_empty_fixture_list_gives_valid_empty_calendar():
    data, events = build([])
    assert events == []
    assert b"BEGIN:VCALENDAR" in data
