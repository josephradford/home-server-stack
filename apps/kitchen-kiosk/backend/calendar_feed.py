"""Merges multiple Google/iCloud iCal feed URLs into one sorted, future-only
event list. Read-only - no event creation."""
import os
from datetime import datetime, timezone

import requests
from flask import Blueprint, jsonify, request
from icalendar import Calendar

calendar_bp = Blueprint('calendar', __name__)

ICAL_URLS = [u.strip() for u in os.getenv('KIOSK_CALENDAR_ICAL_URLS', '').split(',') if u.strip()]


def _to_utc_datetime(value):
    """icalendar gives back either a date or a datetime depending on the
    event; normalize both to a timezone-aware UTC datetime for comparison."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _fetch_events(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    cal = Calendar.from_ical(response.text)
    events = []
    for component in cal.walk('VEVENT'):
        start = component.get('dtstart').dt
        end = component.get('dtend').dt if component.get('dtend') else start
        events.append({
            'title': str(component.get('summary', 'Untitled')),
            'start': _to_utc_datetime(start),
            'end': _to_utc_datetime(end),
            'all_day': not isinstance(start, datetime),
        })
    return events


@calendar_bp.route('/api/calendar/events')
def events():
    limit = request.args.get('limit', default=20, type=int)
    now = datetime.now(timezone.utc)

    all_events = []
    for url in ICAL_URLS:
        try:
            all_events.extend(_fetch_events(url))
        except requests.RequestException:
            continue  # one bad feed shouldn't take down the merged list

    future = [e for e in all_events if e['end'] >= now]
    future.sort(key=lambda e: e['start'])

    return jsonify({'events': [
        {**e, 'start': e['start'].isoformat(), 'end': e['end'].isoformat()}
        for e in future[:limit]
    ]})
