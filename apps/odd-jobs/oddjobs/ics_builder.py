"""Turns Fixtures into an .ics calendar with one VEVENT per played day."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, vDuration

from oddjobs.models import Fixture, Status

_PREFIX = {Status.POSTPONED: "[Postponed] ", Status.ABANDONED: "[Abandoned] "}


def event_uid(calendar_name: str, source_id: str, day_number: int, uid_domain: str) -> str:
    return f"{calendar_name}-{source_id}-d{day_number}@{uid_domain}"


def event_summary(fixture: Fixture, day_number: int) -> str:
    title = _PREFIX.get(fixture.status, "") + fixture.title
    if len(fixture.days) > 1:
        title += f", Day {day_number}"
    return title


def build_calendar(
    *,
    calendar_name: str,
    title: str,
    fixtures: list[Fixture],
    tz: ZoneInfo,
    duration: timedelta,
    uid_domain: str,
    now: datetime | None = None,
) -> bytes:
    now = now or datetime.now(timezone.utc)
    cal = Calendar()
    cal.add("prodid", "-//odd-jobs//sports calendars//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", title)
    cal.add("x-wr-timezone", str(tz))
    cal.add("refresh-interval", vDuration(timedelta(days=1)), parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", "PT24H")

    for fixture in sorted(fixtures, key=lambda f: (f.days[0].date, f.source_id)):
        for number, day in enumerate(fixture.days, start=1):
            # Stored as UTC so clients need no VTIMEZONE; DST is applied here via zoneinfo.
            start = datetime.combine(day.date, day.start, tzinfo=tz).astimezone(timezone.utc)
            event = Event()
            event.add("uid", event_uid(calendar_name, fixture.source_id, number, uid_domain))
            event.add("dtstamp", now)
            event.add("dtstart", start)
            event.add("dtend", start + duration)
            event.add("summary", event_summary(fixture, number))
            if fixture.venue:
                event.add("location", fixture.venue)
            if fixture.description:
                event.add("description", fixture.description)
            if fixture.url:
                event.add("url", fixture.url)
            cal.add_component(event)
    return cal.to_ical()
