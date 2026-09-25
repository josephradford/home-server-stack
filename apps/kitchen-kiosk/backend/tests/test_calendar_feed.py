from datetime import datetime, timedelta, timezone

SAMPLE_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1@example.com
DTSTART:{past}
DTEND:{past_end}
SUMMARY:Past Event
END:VEVENT
BEGIN:VEVENT
UID:2@example.com
DTSTART:{future1}
DTEND:{future1_end}
SUMMARY:Dentist
END:VEVENT
BEGIN:VEVENT
UID:3@example.com
DTSTART:{future2}
DTEND:{future2_end}
SUMMARY:Dinner
END:VEVENT
END:VCALENDAR
"""


def _fmt(dt):
    return dt.strftime('%Y%m%dT%H%M%SZ')


def _sample_ical():
    now = datetime.now(timezone.utc)
    return SAMPLE_ICAL.format(
        past=_fmt(now - timedelta(days=1)),
        past_end=_fmt(now - timedelta(days=1, hours=-1)),
        future1=_fmt(now + timedelta(hours=2)),
        future1_end=_fmt(now + timedelta(hours=3)),
        future2=_fmt(now + timedelta(days=1)),
        future2_end=_fmt(now + timedelta(days=1, hours=1)),
    )


def test_calendar_events_excludes_past_and_sorts_by_start(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = _sample_ical()
    mocker.patch('calendar_feed.requests.get', return_value=mock_response)

    response = client.get('/api/calendar/events')

    assert response.status_code == 200
    titles = [e['title'] for e in response.get_json()['events']]
    assert titles == ['Dentist', 'Dinner']


def test_calendar_events_respects_limit(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = _sample_ical()
    mocker.patch('calendar_feed.requests.get', return_value=mock_response)

    response = client.get('/api/calendar/events?limit=1')

    assert len(response.get_json()['events']) == 1


def test_calendar_events_merges_multiple_feeds(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = _sample_ical()
    mocker.patch('calendar_feed.requests.get', return_value=mock_response)
    mocker.patch('calendar_feed.ICAL_URLS', ['http://a.example/cal.ics', 'http://b.example/cal.ics'])

    response = client.get('/api/calendar/events')

    # two identical feeds merged -> each future event appears twice, still sorted
    assert len(response.get_json()['events']) == 4


def test_calendar_events_fetches_feeds_once_within_cache_ttl(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = _sample_ical()
    mock_get = mocker.patch('calendar_feed.requests.get', return_value=mock_response)

    client.get('/api/calendar/events')
    client.get('/api/calendar/events?limit=1')

    assert mock_get.call_count == 1


RECURRING_ICAL = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:weekly@example.com
DTSTART:{master_start}
DTEND:{master_end}
RRULE:FREQ=WEEKLY;BYDAY={byday}
SUMMARY:Weekly Standup
END:VEVENT
END:VCALENDAR
"""


def test_calendar_events_expands_recurring_events_into_upcoming_occurrences(client, mocker):
    # A weekly event whose ORIGINAL start was two years ago - a naive
    # walk('VEVENT') would see only that two-years-ago DTSTART and the
    # future-only filter would wrongly drop it, even though it recurs
    # every week indefinitely.
    now = datetime.now(timezone.utc)
    master_start = now - timedelta(days=730)
    weekday_code = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'][now.weekday()]

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = RECURRING_ICAL.format(
        master_start=_fmt(master_start),
        master_end=_fmt(master_start + timedelta(hours=1)),
        byday=weekday_code,
    )
    mocker.patch('calendar_feed.requests.get', return_value=mock_response)

    response = client.get('/api/calendar/events')

    titles = [e['title'] for e in response.get_json()['events']]
    assert 'Weekly Standup' in titles


def test_calendar_events_skips_feed_with_unparseable_calendar(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = 'not a valid ical calendar'
    mocker.patch('calendar_feed.requests.get', return_value=mock_response)

    response = client.get('/api/calendar/events')

    assert response.status_code == 200
    assert response.get_json()['events'] == []
