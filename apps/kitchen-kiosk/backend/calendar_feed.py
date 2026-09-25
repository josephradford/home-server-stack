"""Merges multiple Google/iCloud iCal feed URLs into one sorted, future-only
event list. Read-only - no event creation."""
import os
import time
from datetime import datetime, timedelta, timezone

import recurring_ical_events
import requests
from flask import Blueprint, jsonify, request
from icalendar import Calendar

calendar_bp = Blueprint('calendar', __name__)

ICAL_URLS = [u.strip() for u in os.getenv('KIOSK_CALENDAR_ICAL_URLS', '').split(',') if u.strip()]

EVENTS_CACHE_TTL_SECONDS = 60
_events_cache = {'data': None, 'fetched_at': 0}

# How far ahead to expand recurring events. A yearly-recurring event (e.g. an
# anniversary) needs a window at least this wide to produce its next
# occurrence; a year comfortably covers every recurrence frequency in use.
RECURRENCE_WINDOW_DAYS = 365


def _to_utc_datetime(value):
    """icalendar/recurring_ical_events give back either a date or a datetime
    depending on the event; normalize both to a timezone-aware UTC datetime
    for comparison."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _fetch_events(url):
    """Fetch one feed and expand recurring events (RRULE/RDATE/EXDATE) into
    their actual upcoming occurrences. A plain `cal.walk('VEVENT')` only
    returns each recurring event's original master record - often years in
    the past - which the future-only filter would then silently drop even
    though the event recurs indefinitely (e.g. a weekly reminder created
    two years ago)."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    cal = Calendar.from_ical(response.text)

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=RECURRENCE_WINDOW_DAYS)
    occurrences = recurring_ical_events.of(cal).between(now, window_end)

    events = []
    for component in occurrences:
        start = component.get('dtstart').dt
        end = component.get('dtend').dt if component.get('dtend') else start
        events.append({
            'title': str(component.get('summary', 'Untitled')),
            'start': _to_utc_datetime(start),
            'end': _to_utc_datetime(end),
            'all_day': not isinstance(start, datetime),
        })
    return events


def _collect_events():
    now = time.time()
    if _events_cache['data'] is not None and (now - _events_cache['fetched_at']) < EVENTS_CACHE_TTL_SECONDS:
        return _events_cache['data']

    all_events = []
    for url in ICAL_URLS:
        try:
            all_events.extend(_fetch_events(url))
        except (requests.RequestException, ValueError, AttributeError):
            continue  # one bad feed shouldn't take down the merged list

    _events_cache['data'] = all_events
    _events_cache['fetched_at'] = now
    return all_events


@calendar_bp.route('/api/calendar/events')
def events():
    limit = request.args.get('limit', default=20, type=int)
    now = datetime.now(timezone.utc)

    all_events = _collect_events()

    future = [e for e in all_events if e['end'] >= now]
    future.sort(key=lambda e: e['start'])

    return jsonify({'events': [
        {**e, 'start': e['start'].isoformat(), 'end': e['end'].isoformat()}
        for e in future[:limit]
    ]})
