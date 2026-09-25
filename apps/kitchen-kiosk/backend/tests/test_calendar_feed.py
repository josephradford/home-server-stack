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
