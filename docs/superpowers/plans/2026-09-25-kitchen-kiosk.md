# Kitchen Kiosk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted kitchen kiosk — an iPad-mounted photo screensaver with a
light info overlay (time, weather, next calendar events, photo metadata), plus
touch-triggered radio/calendar/recipe panels and scheduled sleep/wake.

**Architecture:** A Flask backend (`kiosk-api`) aggregates weather (proxied from the
existing `homepage-api`), merged iCal calendar feeds, Immich photo selection, and
recipe markdown into one local REST API. A static single-page frontend
(`kiosk-web`) polls that API and renders the idle screensaver plus radio/calendar/
recipe panels, running full-screen in iOS Safari (Add to Home Screen + Guided
Access).

**Tech Stack:** Python 3.11 / Flask (matches `homepage-api`'s existing stack) +
gunicorn, pytest for backend tests; vanilla JS/HTML/CSS frontend (no build step,
consistent with the project's avoidance of unnecessary tooling); Docker Compose +
Traefik for deployment, matching every other service in this repo.

**Spec:** `docs/superpowers/specs/2026-09-25-kitchen-kiosk-design.md`

## Global Constraints

- Local network only — no public/internet-facing exposure (from spec: "Network scope").
- No offline/cached mode required — kiosk does not need to function if the server is down.
- Live-updating via polling; websocket/SSE only if polling proves too slow (not needed for v1).
- Calendar is read-only — no event creation from the kiosk.
- Recipes are hand-edited directly on the server — no in-place editing UI on the kiosk.
- Radio has no auth — just `<audio>` + preset stream URLs.
- Reuse the existing `homepage-api` BOM weather endpoint (`GET /api/bom/weather`) rather than reimplementing BOM access.
- Follow existing repo conventions: Traefik labels per `CLAUDE.md`'s "Traefik Labels for New Services" pattern, `.env.example` updated for new vars, `SERVICES.md` updated, `make validate` must pass.
- Dollar signs in any password/secret values must be escaped as `$$` for Docker Compose.

---

## File Structure

```
apps/kitchen-kiosk/
  backend/
    app.py                # Flask app factory, blueprint registration, /api/health
    config.py              # env var loading
    weather.py              # blueprint: proxies homepage-api BOM endpoint
    calendar_feed.py        # blueprint: merges iCal feeds
    photos.py                # blueprint: Immich photo selection + metadata
    recipes.py               # blueprint: parses recipe markdown folder
    radio.py                  # blueprint: static preset list
    requirements.txt
    Dockerfile
    tests/
      conftest.py
      test_weather.py
      test_calendar_feed.py
      test_photos.py
      test_recipes.py
      test_radio.py
  frontend/
    index.html              # single page, all views as hidden/shown sections
    app.js                   # polling, view state machine, idle timer, sleep/wake
    style.css
docker-compose.kiosk.yml
```

Each backend module is a Flask blueprint with one responsibility, mirroring how
`homepage-api/app.py` groups routes by data source but split into files since this
service has more data sources than `homepage-api`. The frontend stays a single
static bundle (no framework/build step) since the view count is small and this
matches the project's general preference for minimal tooling.

---

## Task 1: Kiosk shell — reboot resilience placeholder

Proves the deployment shape (compose file, Traefik routing, container restart
policy) works before any feature code exists — the brief's explicit first build
step.

**Files:**
- Create: `apps/kitchen-kiosk/frontend/index.html`
- Create: `apps/kitchen-kiosk/backend/app.py`
- Create: `apps/kitchen-kiosk/backend/requirements.txt`
- Create: `apps/kitchen-kiosk/backend/Dockerfile`
- Create: `apps/kitchen-kiosk/backend/tests/conftest.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_app.py`
- Create: `docker-compose.kiosk.yml`
- Modify: `.env.example`
- Modify: `SERVICES.md`
- Modify: `Makefile` (add `docker-compose.kiosk.yml` to `COMPOSE`)

**Interfaces:**
- Produces: `GET /api/health` → `{"status": "healthy"}` (200). Every later blueprint
  task assumes this app factory and health route already exist.
- Produces: Flask app factory `create_app()` in `app.py` that later tasks import
  and register blueprints on via `app.register_blueprint(...)`.

- [ ] **Step 1: Write the failing health check test**

```python
# apps/kitchen-kiosk/backend/tests/conftest.py
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
```

```python
# apps/kitchen-kiosk/backend/tests/test_app.py
def test_health_check_returns_200(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'healthy'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'` (file doesn't exist yet)

- [ ] **Step 3: Write the minimal Flask app factory**

```python
# apps/kitchen-kiosk/backend/app.py
"""
Kitchen Kiosk Backend API
Aggregates weather, calendar, photos, recipes, and radio presets
for the kitchen kiosk frontend.
"""
from flask import Flask, jsonify
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    CORS(app)

    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy'})

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100)
```

```
# apps/kitchen-kiosk/backend/requirements.txt
Flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
icalendar==5.0.11
pytest==7.4.3
pytest-mock==3.12.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 5: Write the placeholder frontend page**

```html
<!-- apps/kitchen-kiosk/frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
  <title>Kitchen Kiosk</title>
  <style>
    html, body { margin: 0; height: 100%; background: #000; color: #fff;
      font-family: -apple-system, sans-serif; display: flex;
      align-items: center; justify-content: center; }
    #status { font-size: 1.2rem; opacity: 0.6; }
  </style>
</head>
<body>
  <div id="status">Kitchen Kiosk — booting…</div>
  <script>
    async function checkBackend() {
      try {
        const res = await fetch('/api/health');
        const data = await res.json();
        document.getElementById('status').textContent =
          data.status === 'healthy' ? 'Kitchen Kiosk — backend connected' : 'Backend unhealthy';
      } catch (e) {
        document.getElementById('status').textContent = 'Kitchen Kiosk — backend unreachable, retrying…';
      }
    }
    checkBackend();
    setInterval(checkBackend, 5000);
  </script>
</body>
</html>
```

- [ ] **Step 6: Write the backend Dockerfile**

```dockerfile
# apps/kitchen-kiosk/backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 kioskuser && chown -R kioskuser:kioskuser /app
USER kioskuser

EXPOSE 5100

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5100/api/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "app:app"]
```

- [ ] **Step 7: Write the compose file**

```yaml
# docker-compose.kiosk.yml
# Kitchen Kiosk
# - kiosk-api: aggregates weather (via homepage-api), calendar, Immich photos,
#              recipes, and radio presets behind one local API.
# - kiosk-web: static frontend served full-screen on the kitchen iPad via
#              Safari "Add to Home Screen" + Guided Access.

services:
  kiosk-api:
    build: ./apps/kitchen-kiosk/backend
    container_name: kiosk-api
    environment:
      HOMEPAGE_API_URL: http://homepage-api:5000
      TIMEZONE: ${TIMEZONE:-UTC}
      KIOSK_CALENDAR_ICAL_URLS: ${KIOSK_CALENDAR_ICAL_URLS:-}
      KIOSK_IMMICH_URL: ${KIOSK_IMMICH_URL:-}
      KIOSK_IMMICH_API_KEY: ${KIOSK_IMMICH_API_KEY:-}
      KIOSK_IMMICH_ALBUM_IDS: ${KIOSK_IMMICH_ALBUM_IDS:-}
    volumes:
      - ./data/kitchen-kiosk/recipes:/recipes:ro
    restart: unless-stopped
    networks:
      - homeserver
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5100/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.kiosk-api.rule=Host(`kiosk-api.${DOMAIN}`)"
      - "traefik.http.routers.kiosk-api.entrypoints=websecure"
      - "traefik.http.routers.kiosk-api.tls=true"
      - "traefik.http.services.kiosk-api.loadbalancer.server.port=5100"

  kiosk-web:
    image: nginx:1.27-alpine
    container_name: kiosk-web
    volumes:
      - ./apps/kitchen-kiosk/frontend:/usr/share/nginx/html:ro
    restart: unless-stopped
    networks:
      - homeserver
    depends_on:
      - kiosk-api
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.kiosk.rule=Host(`kiosk.${DOMAIN}`)"
      - "traefik.http.routers.kiosk.entrypoints=websecure"
      - "traefik.http.routers.kiosk.tls=true"
      - "traefik.http.services.kiosk.loadbalancer.server.port=80"

networks:
  homeserver:
    external: true
    name: home-server-stack_homeserver
```

- [ ] **Step 8: Add env vars to `.env.example`**

Append to `.env.example`:

```
# -----------------------------------------------------------------------------
# Kitchen Kiosk (docker-compose.kiosk.yml)
# -----------------------------------------------------------------------------
# Comma-separated list of Google/iCloud iCal feed URLs to merge for the kiosk calendar panel
KIOSK_CALENDAR_ICAL_URLS=

# Immich instance URL and API key for the kiosk photo slideshow
KIOSK_IMMICH_URL=http://immich-server:2283
KIOSK_IMMICH_API_KEY=your_immich_api_key_here
# Comma-separated Immich album IDs to draw photos from
KIOSK_IMMICH_ALBUM_IDS=
```

- [ ] **Step 9: Add to `Makefile`'s `COMPOSE` variable**

Edit the `COMPOSE` line in `Makefile` to append ` -f docker-compose.kiosk.yml` after
`-f docker-compose.library.yml`.

- [ ] **Step 10: Add to `SERVICES.md`**

Add a "Kitchen Kiosk" section documenting `kiosk-api` and `kiosk-web`, their
purpose, and the `kiosk.${DOMAIN}` / `kiosk-api.${DOMAIN}` routes, following the
existing per-service format already used in that file for `homepage-api`.

- [ ] **Step 11: Validate compose config**

Run: `make validate`
Expected: passes with no syntax errors.

- [ ] **Step 12: Commit**

```bash
git add apps/kitchen-kiosk docker-compose.kiosk.yml .env.example SERVICES.md Makefile
git commit -m "feat: scaffold kitchen kiosk shell (backend health check + placeholder frontend)"
```

---

## Task 2: Radio presets endpoint

Simplest data source (per the brief) — static list, no external calls. Good second
step to prove the blueprint-registration pattern before tackling anything that
calls out to another service.

**Files:**
- Create: `apps/kitchen-kiosk/backend/radio.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_radio.py`
- Modify: `apps/kitchen-kiosk/backend/app.py`

**Interfaces:**
- Consumes: `create_app()` from Task 1.
- Produces: `GET /api/radio/stations` → `{"stations": [{"id": str, "name": str, "stream_url": str}, ...]}`. Later frontend radio panel task consumes this exact shape.

- [ ] **Step 1: Write the failing test**

```python
# apps/kitchen-kiosk/backend/tests/test_radio.py
def test_radio_stations_returns_four_presets(client):
    response = client.get('/api/radio/stations')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data['stations']) == 4
    names = {s['name'] for s in data['stations']}
    assert names == {'ABC Cricket', 'ABC Classic', 'Double J', 'ABC Jazz'}


def test_radio_station_has_required_fields(client):
    response = client.get('/api/radio/stations')
    station = response.get_json()['stations'][0]
    assert 'id' in station
    assert 'name' in station
    assert 'stream_url' in station
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_radio.py -v`
Expected: FAIL — 404 (route doesn't exist)

- [ ] **Step 3: Write the radio blueprint**

```python
# apps/kitchen-kiosk/backend/radio.py
"""Static radio station presets — no auth, no proxying of the stream itself."""
from flask import Blueprint, jsonify

radio_bp = Blueprint('radio', __name__)

# Stream URLs are ABC/Double J's public HLS/MP3 endpoints - no account needed.
STATIONS = [
    {'id': 'abc-cricket', 'name': 'ABC Cricket', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2LRW/mp3/'},
    {'id': 'abc-classic', 'name': 'ABC Classic', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2FMW/mp3/'},
    {'id': 'double-j', 'name': 'Double J', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2DJW/mp3/'},
    {'id': 'abc-jazz', 'name': 'ABC Jazz', 'stream_url': 'https://live-radio01.mediahubaustralia.com/2JZW/mp3/'},
]


@radio_bp.route('/api/radio/stations')
def stations():
    return jsonify({'stations': STATIONS})
```

- [ ] **Step 4: Register the blueprint**

In `apps/kitchen-kiosk/backend/app.py`, add inside `create_app()` before `return app`:

```python
    from radio import radio_bp
    app.register_blueprint(radio_bp)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_radio.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/kitchen-kiosk/backend/radio.py apps/kitchen-kiosk/backend/tests/test_radio.py apps/kitchen-kiosk/backend/app.py
git commit -m "feat: add radio station presets endpoint"
```

> Note: verify the exact ABC/Double J stream URLs against the live streams before
> shipping — these are the commonly published ABC Radio Player HLS/MP3 mount
> points at time of writing but ABC has changed them before. Confirm each with
> `curl -I <url>` returning 200 before relying on it in the frontend.

---

## Task 3: Weather passthrough endpoint

**Files:**
- Create: `apps/kitchen-kiosk/backend/weather.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_weather.py`
- Modify: `apps/kitchen-kiosk/backend/app.py`
- Modify: `apps/kitchen-kiosk/backend/tests/conftest.py`

**Interfaces:**
- Consumes: `create_app()` from Task 1. Reads `HOMEPAGE_API_URL` env var (set in `docker-compose.kiosk.yml` from Task 1).
- Produces: `GET /api/weather` → passthrough of `homepage-api`'s `/api/bom/weather` JSON shape, or `{"error": "..."}` with 502 if `homepage-api` is unreachable.

- [ ] **Step 1: Write the failing tests using a mocked HTTP call**

```python
# apps/kitchen-kiosk/backend/tests/test_weather.py
def test_weather_proxies_homepage_api(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'current': {'temp': 21.5}}
    mocker.patch('weather.requests.get', return_value=mock_response)

    response = client.get('/api/weather')

    assert response.status_code == 200
    assert response.get_json() == {'current': {'temp': 21.5}}


def test_weather_returns_502_when_homepage_api_unreachable(client, mocker):
    mocker.patch('weather.requests.get', side_effect=ConnectionError('refused'))

    response = client.get('/api/weather')

    assert response.status_code == 502
    assert 'error' in response.get_json()
```

- [ ] **Step 2: Add `pytest-mock`'s `mocker` fixture requirement check and env var to conftest**

`pytest-mock` is already in `requirements.txt` from Task 1 (provides the `mocker`
fixture used above — no new dependency). Add the env var the module needs to
`conftest.py`, above the `from app import create_app` line:

```python
os.environ['HOMEPAGE_API_URL'] = 'http://homepage-api:5000'
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_weather.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'weather'`

- [ ] **Step 4: Write the weather blueprint**

```python
# apps/kitchen-kiosk/backend/weather.py
"""Proxies the existing homepage-api BOM weather endpoint so the kiosk
doesn't need its own BOM integration."""
import os
import requests
from flask import Blueprint, jsonify

weather_bp = Blueprint('weather', __name__)

HOMEPAGE_API_URL = os.getenv('HOMEPAGE_API_URL', 'http://homepage-api:5000')


@weather_bp.route('/api/weather')
def weather():
    try:
        response = requests.get(f'{HOMEPAGE_API_URL}/api/bom/weather', timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        return jsonify({'error': f'weather backend unreachable: {e}'}), 502
```

- [ ] **Step 5: Register the blueprint**

In `apps/kitchen-kiosk/backend/app.py`, add alongside the radio registration:

```python
    from weather import weather_bp
    app.register_blueprint(weather_bp)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_weather.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/kitchen-kiosk/backend/weather.py apps/kitchen-kiosk/backend/tests/test_weather.py apps/kitchen-kiosk/backend/app.py apps/kitchen-kiosk/backend/tests/conftest.py
git commit -m "feat: add weather endpoint proxying homepage-api BOM data"
```

---

## Task 4: Calendar feed merge endpoint

**Files:**
- Create: `apps/kitchen-kiosk/backend/calendar_feed.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_calendar_feed.py`
- Modify: `apps/kitchen-kiosk/backend/app.py`
- Modify: `apps/kitchen-kiosk/backend/tests/conftest.py`

**Interfaces:**
- Consumes: `create_app()` from Task 1. Reads `KIOSK_CALENDAR_ICAL_URLS` (comma-separated) env var.
- Produces: `GET /api/calendar/events?limit=N` → `{"events": [{"title": str, "start": ISO8601 str, "end": ISO8601 str, "all_day": bool}, ...]}` sorted by `start` ascending, only future/in-progress events, limited to `limit` (default 20). Later frontend idle-overlay and calendar-panel tasks consume this shape.

- [ ] **Step 1: Write the failing tests**

```python
# apps/kitchen-kiosk/backend/tests/test_calendar_feed.py
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
```

- [ ] **Step 2: Add `icalendar` dependency note and env var**

`icalendar==5.0.11` is already in `requirements.txt` from Task 1. Add to
`conftest.py`, above the `from app import create_app` line:

```python
os.environ['KIOSK_CALENDAR_ICAL_URLS'] = 'http://a.example/cal.ics'
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_calendar_feed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'calendar_feed'`

- [ ] **Step 4: Write the calendar blueprint**

```python
# apps/kitchen-kiosk/backend/calendar_feed.py
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
```

- [ ] **Step 5: Register the blueprint**

In `apps/kitchen-kiosk/backend/app.py`, add:

```python
    from calendar_feed import calendar_bp
    app.register_blueprint(calendar_bp)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_calendar_feed.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/kitchen-kiosk/backend/calendar_feed.py apps/kitchen-kiosk/backend/tests/test_calendar_feed.py apps/kitchen-kiosk/backend/app.py apps/kitchen-kiosk/backend/tests/conftest.py
git commit -m "feat: add merged calendar events endpoint"
```

---

## Task 5: Recipe markdown parser endpoint

**Files:**
- Create: `apps/kitchen-kiosk/backend/recipes.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_recipes.py`
- Modify: `apps/kitchen-kiosk/backend/app.py`
- Modify: `apps/kitchen-kiosk/backend/tests/conftest.py`
- Modify: `apps/kitchen-kiosk/backend/requirements.txt`

**Interfaces:**
- Consumes: `create_app()` from Task 1. Reads `KIOSK_RECIPES_DIR` env var (default `/recipes`, matching the volume mount from Task 1's compose file).
- Produces: `GET /api/recipes` → `{"recipes": [{"id": str, "title": str}, ...]}`. `GET /api/recipes/<id>` → `{"id": str, "title": str, "ingredients": [str, ...], "steps": [str, ...]}` or 404.

Recipe file format (one `.md` file per recipe, hand-edited on the server):

```markdown
# Title

## Ingredients
- ingredient one
- ingredient two

## Steps
1. step one
2. step two
```

- [ ] **Step 1: Write the failing tests**

```python
# apps/kitchen-kiosk/backend/tests/test_recipes.py
RECIPE_MD = """# Banana Bread

## Ingredients
- 3 ripe bananas
- 1 cup sugar
- 2 cups flour

## Steps
1. Mash the bananas
2. Mix everything together
3. Bake at 180C for 50 minutes
"""


def test_recipes_list_returns_titles(client, tmp_path, monkeypatch):
    (tmp_path / 'banana-bread.md').write_text(RECIPE_MD)
    monkeypatch.setattr('recipes.RECIPES_DIR', str(tmp_path))

    response = client.get('/api/recipes')

    assert response.status_code == 200
    recipes = response.get_json()['recipes']
    assert recipes == [{'id': 'banana-bread', 'title': 'Banana Bread'}]


def test_recipe_detail_parses_ingredients_and_steps(client, tmp_path, monkeypatch):
    (tmp_path / 'banana-bread.md').write_text(RECIPE_MD)
    monkeypatch.setattr('recipes.RECIPES_DIR', str(tmp_path))

    response = client.get('/api/recipes/banana-bread')

    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'Banana Bread'
    assert data['ingredients'] == ['3 ripe bananas', '1 cup sugar', '2 cups flour']
    assert data['steps'] == [
        'Mash the bananas',
        'Mix everything together',
        'Bake at 180C for 50 minutes',
    ]


def test_recipe_detail_404_for_missing_recipe(client, tmp_path, monkeypatch):
    monkeypatch.setattr('recipes.RECIPES_DIR', str(tmp_path))

    response = client.get('/api/recipes/does-not-exist')

    assert response.status_code == 404
```

- [ ] **Step 2: Add `markdown-it-py` dependency and env var**

Add to `apps/kitchen-kiosk/backend/requirements.txt`:

```
markdown-it-py==3.0.0
```

Add to `conftest.py`, above the `from app import create_app` line:

```python
os.environ['KIOSK_RECIPES_DIR'] = '/tmp/kiosk-test-recipes'
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && pip install -r requirements.txt && python -m pytest tests/test_recipes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'recipes'`

- [ ] **Step 4: Write the recipes blueprint**

```python
# apps/kitchen-kiosk/backend/recipes.py
"""Parses a folder of hand-edited recipe markdown files into structured JSON.
No in-place editing UI - files are edited directly on the server."""
import os
import re
from pathlib import Path

from flask import Blueprint, jsonify

recipes_bp = Blueprint('recipes', __name__)

RECIPES_DIR = os.getenv('KIOSK_RECIPES_DIR', '/recipes')


def _recipe_path(recipe_id):
    return Path(RECIPES_DIR) / f'{recipe_id}.md'


def _parse_recipe(text):
    """Expects:
    # Title
    ## Ingredients
    - item
    ## Steps
    1. step
    """
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else 'Untitled'

    ingredients_match = re.search(r'##\s*Ingredients\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
    ingredients = []
    if ingredients_match:
        ingredients = [
            line.lstrip('-* ').strip()
            for line in ingredients_match.group(1).strip().splitlines()
            if line.strip()
        ]

    steps_match = re.search(r'##\s*Steps\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
    steps = []
    if steps_match:
        steps = [
            re.sub(r'^\d+\.\s*', '', line).strip()
            for line in steps_match.group(1).strip().splitlines()
            if line.strip()
        ]

    return title, ingredients, steps


@recipes_bp.route('/api/recipes')
def list_recipes():
    result = []
    recipes_dir = Path(RECIPES_DIR)
    if recipes_dir.is_dir():
        for path in sorted(recipes_dir.glob('*.md')):
            text = path.read_text()
            title, _, _ = _parse_recipe(text)
            result.append({'id': path.stem, 'title': title})
    return jsonify({'recipes': result})


@recipes_bp.route('/api/recipes/<recipe_id>')
def recipe_detail(recipe_id):
    path = _recipe_path(recipe_id)
    if not path.is_file():
        return jsonify({'error': 'recipe not found'}), 404

    title, ingredients, steps = _parse_recipe(path.read_text())
    return jsonify({'id': recipe_id, 'title': title, 'ingredients': ingredients, 'steps': steps})
```

- [ ] **Step 5: Register the blueprint**

In `apps/kitchen-kiosk/backend/app.py`, add:

```python
    from recipes import recipes_bp
    app.register_blueprint(recipes_bp)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_recipes.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/kitchen-kiosk/backend/recipes.py apps/kitchen-kiosk/backend/tests/test_recipes.py apps/kitchen-kiosk/backend/app.py apps/kitchen-kiosk/backend/tests/conftest.py apps/kitchen-kiosk/backend/requirements.txt
git commit -m "feat: add recipe markdown parsing endpoints"
```

---

## Task 6: Immich photo selection endpoint

**Files:**
- Create: `apps/kitchen-kiosk/backend/photos.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_photos.py`
- Modify: `apps/kitchen-kiosk/backend/app.py`
- Modify: `apps/kitchen-kiosk/backend/tests/conftest.py`

**Interfaces:**
- Consumes: `create_app()` from Task 1. Reads `KIOSK_IMMICH_URL`, `KIOSK_IMMICH_API_KEY`, `KIOSK_IMMICH_ALBUM_IDS` (comma-separated) env vars.
- Produces: `GET /api/photos/random` → `{"asset_id": str, "image_url": str, "taken_at": ISO8601 str | null, "place": str | null}` or 502 if Immich is unreachable, or 404 if no configured albums contain any assets.

- [ ] **Step 1: Write the failing tests**

```python
# apps/kitchen-kiosk/backend/tests/test_photos.py
IMMICH_ALBUM_RESPONSE = {
    'assets': [
        {
            'id': 'asset-1',
            'exifInfo': {'dateTimeOriginal': '2025-03-01T10:00:00.000Z', 'city': 'Sydney'},
        },
        {
            'id': 'asset-2',
            'exifInfo': {'dateTimeOriginal': None, 'city': None},
        },
    ]
}


def test_random_photo_returns_asset_with_metadata(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = IMMICH_ALBUM_RESPONSE
    mocker.patch('photos.requests.get', return_value=mock_response)
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[0])

    response = client.get('/api/photos/random')

    assert response.status_code == 200
    data = response.get_json()
    assert data['asset_id'] == 'asset-1'
    assert data['taken_at'] == '2025-03-01T10:00:00.000Z'
    assert data['place'] == 'Sydney'
    assert data['image_url'].endswith('/api/assets/asset-1/thumbnail?size=preview')


def test_random_photo_handles_missing_metadata(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = IMMICH_ALBUM_RESPONSE
    mocker.patch('photos.requests.get', return_value=mock_response)
    mocker.patch('photos.random.choice', side_effect=lambda seq: seq[1])

    response = client.get('/api/photos/random')

    data = response.get_json()
    assert data['asset_id'] == 'asset-2'
    assert data['taken_at'] is None
    assert data['place'] is None


def test_random_photo_502_when_immich_unreachable(client, mocker):
    mocker.patch('photos.requests.get', side_effect=ConnectionError('refused'))

    response = client.get('/api/photos/random')

    assert response.status_code == 502


def test_random_photo_404_when_no_assets(client, mocker):
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'assets': []}
    mocker.patch('photos.requests.get', return_value=mock_response)

    response = client.get('/api/photos/random')

    assert response.status_code == 404
```

- [ ] **Step 2: Add env vars to conftest**

Add to `conftest.py`, above the `from app import create_app` line:

```python
os.environ['KIOSK_IMMICH_URL'] = 'http://immich-server:2283'
os.environ['KIOSK_IMMICH_API_KEY'] = 'test-immich-key'
os.environ['KIOSK_IMMICH_ALBUM_IDS'] = 'album-1'
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_photos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'photos'`

- [ ] **Step 4: Write the photos blueprint**

```python
# apps/kitchen-kiosk/backend/photos.py
"""Queries the Immich API directly for a random photo from configured
album(s), returning an image URL plus date/place metadata."""
import os
import random

import requests
from flask import Blueprint, jsonify

photos_bp = Blueprint('photos', __name__)

IMMICH_URL = os.getenv('KIOSK_IMMICH_URL', 'http://immich-server:2283')
IMMICH_API_KEY = os.getenv('KIOSK_IMMICH_API_KEY', '')
ALBUM_IDS = [a.strip() for a in os.getenv('KIOSK_IMMICH_ALBUM_IDS', '').split(',') if a.strip()]


def _headers():
    return {'x-api-key': IMMICH_API_KEY}


def _collect_assets():
    assets = []
    for album_id in ALBUM_IDS:
        response = requests.get(f'{IMMICH_URL}/api/albums/{album_id}', headers=_headers(), timeout=10)
        response.raise_for_status()
        assets.extend(response.json().get('assets', []))
    return assets


@photos_bp.route('/api/photos/random')
def random_photo():
    try:
        assets = _collect_assets()
    except requests.RequestException as e:
        return jsonify({'error': f'immich unreachable: {e}'}), 502

    if not assets:
        return jsonify({'error': 'no photos available in configured albums'}), 404

    asset = random.choice(assets)
    exif = asset.get('exifInfo') or {}

    return jsonify({
        'asset_id': asset['id'],
        'image_url': f'{IMMICH_URL}/api/assets/{asset["id"]}/thumbnail?size=preview',
        'taken_at': exif.get('dateTimeOriginal'),
        'place': exif.get('city'),
    })
```

- [ ] **Step 5: Register the blueprint**

In `apps/kitchen-kiosk/backend/app.py`, add:

```python
    from photos import photos_bp
    app.register_blueprint(photos_bp)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_photos.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/kitchen-kiosk/backend/photos.py apps/kitchen-kiosk/backend/tests/test_photos.py apps/kitchen-kiosk/backend/app.py apps/kitchen-kiosk/backend/tests/conftest.py
git commit -m "feat: add Immich random photo endpoint with metadata"
```

> Note: the frontend must send the Immich image itself through `<img>` `src`
> pointing at `image_url`, which requires the browser to reach Immich directly (or
> the kiosk-api to proxy image bytes if Immich isn't reachable from the iPad's
> network segment). Confirm during Task 7 which is needed; if the iPad can reach
> `immich-server` directly on the LAN, no proxying is required since `image_url`
> is already a full URL to `KIOSK_IMMICH_URL`. The `x-api-key` header can't be
> attached to a plain `<img>` tag — if Immich requires it for asset thumbnails,
> add an image-proxy route to `photos.py` that fetches the bytes server-side and
> streams them back unauthenticated. Verify this against the deployed Immich
> instance's actual auth requirements before building the frontend photo view.

---

## Task 7: Frontend idle screensaver view

**Files:**
- Modify: `apps/kitchen-kiosk/frontend/index.html`
- Create: `apps/kitchen-kiosk/frontend/app.js`
- Create: `apps/kitchen-kiosk/frontend/style.css`

**Interfaces:**
- Consumes: `GET /api/weather`, `GET /api/calendar/events?limit=2`, `GET /api/photos/random` (Tasks 3, 4, 6).
- Produces: a global `KioskApp.showIdle()` / `KioskApp.showPanel(name)` pair of functions that Tasks 8-10 call to switch views, and a `KioskApp.resetIdleTimer()` function Tasks 8-10 call on touch inside a panel.

This view has no backend logic to unit test; verification is manual against the
running containers, matching how `homepage`'s dashboard UI is verified elsewhere
in this repo (no frontend test suite exists in this codebase to follow).

- [ ] **Step 1: Replace the placeholder page with the full shell**

```html
<!-- apps/kitchen-kiosk/frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
  <title>Kitchen Kiosk</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="view-idle" class="view">
    <img id="idle-photo" src="" alt="">
    <div class="overlay overlay-top-left">
      <div id="overlay-time"></div>
      <div id="overlay-date"></div>
    </div>
    <div class="overlay overlay-top-right">
      <div id="overlay-weather"></div>
    </div>
    <div class="overlay overlay-bottom-left">
      <div id="overlay-photo-meta"></div>
    </div>
    <div class="overlay overlay-bottom-right">
      <div id="overlay-events"></div>
    </div>
  </div>

  <div id="view-nav" class="view hidden">
    <button data-panel="radio">Radio</button>
    <button data-panel="calendar">Calendar</button>
    <button data-panel="recipes">Recipes</button>
  </div>

  <div id="view-radio" class="view panel hidden"></div>
  <div id="view-calendar" class="view panel hidden"></div>
  <div id="view-recipes" class="view panel hidden"></div>

  <div id="view-sleep" class="view hidden"></div>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write the polling + view-switching core**

```css
/* apps/kitchen-kiosk/frontend/style.css */
html, body { margin: 0; height: 100%; background: #000; color: #fff;
  font-family: -apple-system, sans-serif; overflow: hidden; }
.view { position: fixed; inset: 0; }
.hidden { display: none; }
#idle-photo { width: 100%; height: 100%; object-fit: cover; }
.overlay { position: absolute; padding: 12px 16px; font-size: 1rem;
  text-shadow: 0 1px 4px rgba(0,0,0,0.8); }
.overlay-top-left { top: 0; left: 0; }
.overlay-top-right { top: 0; right: 0; text-align: right; }
.overlay-bottom-left { bottom: 0; left: 0; }
.overlay-bottom-right { bottom: 0; right: 0; text-align: right; }
#view-sleep { background: #000; }
```

```javascript
// apps/kitchen-kiosk/frontend/app.js
const KioskApp = (() => {
  const IDLE_TIMEOUT_MS = 30 * 1000;       // return to screensaver after 30s of no touch on idle/nav
  const PANEL_TIMEOUT_MS = 5 * 60 * 1000;  // panels get their own longer timeout
  const PHOTO_INTERVAL_MS = 60 * 1000;
  const POLL_INTERVAL_MS = 30 * 1000;

  let idleTimer = null;
  let currentView = 'idle';

  function $(id) { return document.getElementById(id); }

  function showView(id) {
    document.querySelectorAll('.view').forEach(el => el.classList.add('hidden'));
    $(id).classList.remove('hidden');
  }

  function showIdle() {
    currentView = 'idle';
    showView('view-idle');
    resetIdleTimer();
  }

  function showNav() {
    currentView = 'nav';
    showView('view-nav');
    resetIdleTimer();
  }

  function showPanel(name) {
    currentView = 'panel';
    showView(`view-${name}`);
    resetIdleTimer();
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    // Idle timer only runs on the idle/nav views - an open panel gets its own
    // longer timeout instead, so a recipe never gets interrupted mid-read.
    const timeout = currentView === 'panel' ? PANEL_TIMEOUT_MS : IDLE_TIMEOUT_MS;
    idleTimer = setTimeout(showIdle, timeout);
  }

  async function refreshOverlay() {
    try {
      const [weather, calendar] = await Promise.all([
        fetch('/api/weather').then(r => r.json()),
        fetch('/api/calendar/events?limit=2').then(r => r.json()),
      ]);
      $('overlay-weather').textContent = weather.current
        ? `${weather.current.temp}°C` : 'Weather unavailable';
      $('overlay-events').innerHTML = calendar.events
        .map(e => `${e.title} — ${new Date(e.start).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`)
        .join('<br>');
    } catch (e) {
      console.error('overlay refresh failed', e);
    }
  }

  async function refreshPhoto() {
    try {
      const photo = await fetch('/api/photos/random').then(r => r.json());
      $('idle-photo').src = photo.image_url;
      const meta = [photo.taken_at ? new Date(photo.taken_at).toLocaleDateString() : null, photo.place]
        .filter(Boolean).join(' · ');
      $('overlay-photo-meta').textContent = meta;
    } catch (e) {
      console.error('photo refresh failed', e);
    }
  }

  function updateClock() {
    const now = new Date();
    $('overlay-time').textContent = now.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    $('overlay-date').textContent = now.toLocaleDateString([], {weekday: 'long', month: 'long', day: 'numeric'});
  }

  function init() {
    document.addEventListener('touchstart', () => {
      if (currentView === 'idle') { showNav(); return; }
      resetIdleTimer();
    });

    document.querySelectorAll('#view-nav button').forEach(btn => {
      btn.addEventListener('click', () => showPanel(btn.dataset.panel));
    });

    updateClock();
    setInterval(updateClock, 1000);
    refreshOverlay();
    setInterval(refreshOverlay, POLL_INTERVAL_MS);
    refreshPhoto();
    setInterval(refreshPhoto, PHOTO_INTERVAL_MS);

    showIdle();
  }

  document.addEventListener('DOMContentLoaded', init);

  return { showIdle, showPanel, resetIdleTimer };
})();
```

- [ ] **Step 3: Manually verify against the running stack**

Run: `make validate && docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.kiosk.yml up -d kiosk-api kiosk-web`

Open `https://kiosk.${DOMAIN}` in a browser. Confirm:
- The idle view shows a photo, clock updating every second, weather, and next events.
- Touching anywhere shows the Radio/Calendar/Recipes nav buttons.
- Waiting 30s on the nav view returns to idle.

- [ ] **Step 4: Commit**

```bash
git add apps/kitchen-kiosk/frontend
git commit -m "feat: build kiosk idle screensaver view with overlay and idle timer"
```

---

## Task 8: Radio panel

**Files:**
- Modify: `apps/kitchen-kiosk/frontend/index.html`
- Modify: `apps/kitchen-kiosk/frontend/app.js`

**Interfaces:**
- Consumes: `GET /api/radio/stations` (Task 2), `KioskApp.resetIdleTimer()` (Task 7).

- [ ] **Step 1: Add the radio panel markup**

In `index.html`, replace `<div id="view-radio" class="view panel hidden"></div>` with:

```html
<div id="view-radio" class="view panel hidden">
  <button class="back-btn" onclick="KioskApp.showIdle()">← Back</button>
  <ul id="radio-list"></ul>
  <audio id="radio-audio"></audio>
</div>
```

- [ ] **Step 2: Add the radio panel logic**

Add to `app.js`, inside the `KioskApp` IIFE before `function init()`:

```javascript
  let currentStation = null;

  async function loadRadioPanel() {
    const list = $('radio-list');
    if (list.dataset.loaded) return;
    const { stations } = await fetch('/api/radio/stations').then(r => r.json());
    list.innerHTML = stations.map(s =>
      `<li data-url="${s.stream_url}" data-id="${s.id}">${s.name}</li>`
    ).join('');
    list.dataset.loaded = 'true';

    list.addEventListener('click', (e) => {
      const li = e.target.closest('li');
      if (!li) return;
      resetIdleTimer();
      const audio = $('radio-audio');
      if (currentStation === li.dataset.id) {
        audio.pause();
        currentStation = null;
        li.classList.remove('playing');
      } else {
        list.querySelectorAll('li').forEach(el => el.classList.remove('playing'));
        audio.src = li.dataset.url;
        audio.play();
        currentStation = li.dataset.id;
        li.classList.add('playing');
      }
    });
  }
```

Update `showPanel` to call it:

```javascript
  function showPanel(name) {
    currentView = 'panel';
    showView(`view-${name}`);
    if (name === 'radio') loadRadioPanel();
    resetIdleTimer();
  }
```

- [ ] **Step 3: Add minimal styling**

Append to `style.css`:

```css
.panel { background: #111; padding: 24px; box-sizing: border-box; }
.back-btn { font-size: 1.2rem; background: none; color: #fff; border: none; margin-bottom: 16px; }
#radio-list { list-style: none; padding: 0; font-size: 1.5rem; }
#radio-list li { padding: 16px; border-bottom: 1px solid #333; }
#radio-list li.playing { color: #4ade80; }
```

- [ ] **Step 4: Manually verify**

Run: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.kiosk.yml restart kiosk-web`

Open `https://kiosk.${DOMAIN}`, touch idle screen, tap Radio, tap a station.
Confirm audio plays and tapping again stops it.

- [ ] **Step 5: Commit**

```bash
git add apps/kitchen-kiosk/frontend
git commit -m "feat: add radio panel with tap-to-play/stop presets"
```

---

## Task 9: Calendar panel

**Files:**
- Modify: `apps/kitchen-kiosk/frontend/index.html`
- Modify: `apps/kitchen-kiosk/frontend/app.js`

**Interfaces:**
- Consumes: `GET /api/calendar/events?limit=20` (Task 4), `KioskApp.resetIdleTimer()` (Task 7).

- [ ] **Step 1: Add the calendar panel markup**

In `index.html`, replace `<div id="view-calendar" class="view panel hidden"></div>` with:

```html
<div id="view-calendar" class="view panel hidden">
  <button class="back-btn" onclick="KioskApp.showIdle()">← Back</button>
  <ul id="calendar-list"></ul>
</div>
```

- [ ] **Step 2: Add the calendar panel logic**

Add to `app.js`, inside the `KioskApp` IIFE:

```javascript
  async function loadCalendarPanel() {
    const list = $('calendar-list');
    const { events } = await fetch('/api/calendar/events?limit=20').then(r => r.json());
    list.innerHTML = events.map(e => {
      const start = new Date(e.start);
      const when = e.all_day
        ? start.toLocaleDateString([], {weekday: 'short', month: 'short', day: 'numeric'})
        : start.toLocaleString([], {weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
      return `<li><strong>${e.title}</strong><br>${when}</li>`;
    }).join('') || '<li>No upcoming events</li>';
  }
```

Update `showPanel` to call it:

```javascript
  function showPanel(name) {
    currentView = 'panel';
    showView(`view-${name}`);
    if (name === 'radio') loadRadioPanel();
    if (name === 'calendar') loadCalendarPanel();
    resetIdleTimer();
  }
```

- [ ] **Step 3: Add minimal styling**

Append to `style.css`:

```css
#calendar-list { list-style: none; padding: 0; font-size: 1.3rem; }
#calendar-list li { padding: 16px; border-bottom: 1px solid #333; }
```

- [ ] **Step 4: Manually verify**

Open `https://kiosk.${DOMAIN}`, touch idle screen, tap Calendar. Confirm the full
list of upcoming events shows with correct dates/times, matching what the idle
overlay's next-2-events summary shows for the soonest ones.

- [ ] **Step 5: Commit**

```bash
git add apps/kitchen-kiosk/frontend
git commit -m "feat: add calendar panel showing full upcoming event list"
```

---

## Task 10: Recipes panel

**Files:**
- Modify: `apps/kitchen-kiosk/frontend/index.html`
- Modify: `apps/kitchen-kiosk/frontend/app.js`

**Interfaces:**
- Consumes: `GET /api/recipes`, `GET /api/recipes/<id>` (Task 5), `KioskApp.resetIdleTimer()` (Task 7).

- [ ] **Step 1: Add the recipes panel markup**

In `index.html`, replace `<div id="view-recipes" class="view panel hidden"></div>` with:

```html
<div id="view-recipes" class="view panel hidden">
  <button class="back-btn" onclick="KioskApp.showIdle()">← Back</button>
  <div id="recipes-list-view">
    <ul id="recipes-list"></ul>
  </div>
  <div id="recipes-detail-view" class="hidden">
    <button class="back-btn" id="recipes-back-to-list">← Recipes</button>
    <h1 id="recipe-title"></h1>
    <h2>Ingredients</h2>
    <ul id="recipe-ingredients"></ul>
    <h2>Steps</h2>
    <ol id="recipe-steps"></ol>
  </div>
</div>
```

- [ ] **Step 2: Add the recipes panel logic**

Add to `app.js`, inside the `KioskApp` IIFE:

```javascript
  async function loadRecipesPanel() {
    $('recipes-detail-view').classList.add('hidden');
    $('recipes-list-view').classList.remove('hidden');

    const list = $('recipes-list');
    const { recipes } = await fetch('/api/recipes').then(r => r.json());
    list.innerHTML = recipes.map(r => `<li data-id="${r.id}">${r.title}</li>`).join('');

    list.onclick = async (e) => {
      const li = e.target.closest('li');
      if (!li) return;
      resetIdleTimer();
      const recipe = await fetch(`/api/recipes/${li.dataset.id}`).then(r => r.json());
      $('recipe-title').textContent = recipe.title;
      $('recipe-ingredients').innerHTML = recipe.ingredients.map(i => `<li>${i}</li>`).join('');
      $('recipe-steps').innerHTML = recipe.steps.map(s => `<li>${s}</li>`).join('');
      $('recipes-list-view').classList.add('hidden');
      $('recipes-detail-view').classList.remove('hidden');
    };
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('recipes-back-to-list').addEventListener('click', () => {
      resetIdleTimer();
      $('recipes-detail-view').classList.add('hidden');
      $('recipes-list-view').classList.remove('hidden');
    });
  });
```

Update `showPanel` to call it:

```javascript
  function showPanel(name) {
    currentView = 'panel';
    showView(`view-${name}`);
    if (name === 'radio') loadRadioPanel();
    if (name === 'calendar') loadCalendarPanel();
    if (name === 'recipes') loadRecipesPanel();
    resetIdleTimer();
  }
```

- [ ] **Step 3: Add minimal styling**

Append to `style.css`:

```css
#recipes-list { list-style: none; padding: 0; font-size: 1.3rem; }
#recipes-list li { padding: 16px; border-bottom: 1px solid #333; }
#recipes-detail-view { font-size: 1.2rem; overflow-y: auto; height: calc(100% - 60px); }
```

- [ ] **Step 4: Manually verify**

Add a test recipe file to `data/kitchen-kiosk/recipes/test-recipe.md` on the server
matching the format from Task 5, restart `kiosk-api`, then open the Recipes panel
on the kiosk and confirm it lists and displays correctly.

- [ ] **Step 5: Commit**

```bash
git add apps/kitchen-kiosk/frontend
git commit -m "feat: add recipes panel with list and detail views"
```

---

## Task 11: Scheduled sleep/wake

**Files:**
- Modify: `apps/kitchen-kiosk/frontend/app.js`
- Modify: `.env.example`
- Modify: `docker-compose.kiosk.yml`

**Interfaces:**
- Consumes: `KIOSK_SLEEP_START` / `KIOSK_SLEEP_END` env vars (24h `HH:MM`, local time), injected into the frontend via a small config endpoint since static HTML can't read server env vars directly.
- Produces: `KioskApp` sleep behavior — screen goes to a black `view-sleep` view during the configured window, any touch instantly wakes to idle.

This adds a `/api/config` endpoint to `kiosk-api` (in `app.py` directly, since it's
a single trivial route with no dependencies worth its own module) rather than only
touching the frontend.

- [ ] **Step 1: Write the failing test for the config endpoint**

```python
# apps/kitchen-kiosk/backend/tests/test_app.py
# (add to the existing file)
def test_config_returns_sleep_window(client, monkeypatch):
    monkeypatch.setenv('KIOSK_SLEEP_START', '23:00')
    monkeypatch.setenv('KIOSK_SLEEP_END', '07:00')

    response = client.get('/api/config')

    assert response.status_code == 200
    assert response.get_json() == {'sleep_start': '23:00', 'sleep_end': '07:00'}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_app.py -v`
Expected: FAIL — 404 (route doesn't exist)

- [ ] **Step 3: Add the config route**

In `apps/kitchen-kiosk/backend/app.py`, add inside `create_app()`, after the health
check route:

```python
    @app.route('/api/config')
    def config():
        return jsonify({
            'sleep_start': os.getenv('KIOSK_SLEEP_START', '23:00'),
            'sleep_end': os.getenv('KIOSK_SLEEP_END', '07:00'),
        })
```

Add `import os` to the top of `app.py` if not already present (it isn't, from
Task 1).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 5: Add sleep scheduling to the frontend**

Add to `app.js`, inside the `KioskApp` IIFE:

```javascript
  let sleepWindow = { sleep_start: '23:00', sleep_end: '07:00' };
  let isSleeping = false;

  function parseTimeToMinutes(hhmm) {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
  }

  function isWithinSleepWindow(now) {
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    const start = parseTimeToMinutes(sleepWindow.sleep_start);
    const end = parseTimeToMinutes(sleepWindow.sleep_end);
    // overnight windows wrap past midnight (e.g. 23:00 -> 07:00)
    return start > end
      ? (nowMinutes >= start || nowMinutes < end)
      : (nowMinutes >= start && nowMinutes < end);
  }

  function enterSleep() {
    if (isSleeping) return;
    isSleeping = true;
    showView('view-sleep');
  }

  function wake() {
    isSleeping = false;
    showIdle();
  }

  function checkSleepSchedule() {
    if (isWithinSleepWindow(new Date())) {
      enterSleep();
    } else if (isSleeping) {
      wake();
    }
  }
```

Update `init()` to load config and start the schedule check, and update the touch
listener to always wake first:

```javascript
  function init() {
    document.addEventListener('touchstart', () => {
      if (isSleeping) { wake(); return; }   // touch always wakes instantly, regardless of schedule
      if (currentView === 'idle') { showNav(); return; }
      resetIdleTimer();
    });

    document.querySelectorAll('#view-nav button').forEach(btn => {
      btn.addEventListener('click', () => showPanel(btn.dataset.panel));
    });

    fetch('/api/config').then(r => r.json()).then(cfg => { sleepWindow = cfg; });

    updateClock();
    setInterval(updateClock, 1000);
    refreshOverlay();
    setInterval(refreshOverlay, POLL_INTERVAL_MS);
    refreshPhoto();
    setInterval(refreshPhoto, PHOTO_INTERVAL_MS);
    checkSleepSchedule();
    setInterval(checkSleepSchedule, 60 * 1000);

    showIdle();
  }
```

- [ ] **Step 6: Add sleep view styling**

Append to `style.css`:

```css
#view-sleep { background: #000; }
```

(Already effectively black via `body` background — this rule documents intent
explicitly rather than relying on inheritance.)

- [ ] **Step 7: Add env vars to `.env.example`**

Append to the Kitchen Kiosk section added in Task 1:

```
# Overnight sleep window (24h HH:MM, local server time) - screen sleeps during this window
KIOSK_SLEEP_START=23:00
KIOSK_SLEEP_END=07:00
```

- [ ] **Step 8: Pass the env vars through in the compose file**

In `docker-compose.kiosk.yml`, add to `kiosk-api`'s `environment:` block:

```yaml
      KIOSK_SLEEP_START: ${KIOSK_SLEEP_START:-23:00}
      KIOSK_SLEEP_END: ${KIOSK_SLEEP_END:-07:00}
```

- [ ] **Step 9: Validate and manually verify**

Run: `make validate`

Manually set `KIOSK_SLEEP_START`/`KIOSK_SLEEP_END` to bracket the current time,
restart `kiosk-api`, reload the kiosk page, and confirm it goes to a black sleep
screen, and that touching it immediately wakes to idle regardless of the window.

- [ ] **Step 10: Commit**

```bash
git add apps/kitchen-kiosk/backend/app.py apps/kitchen-kiosk/backend/tests/test_app.py apps/kitchen-kiosk/frontend .env.example docker-compose.kiosk.yml
git commit -m "feat: add scheduled overnight sleep/wake with instant touch-wake"
```

---

## Task 12: Wi-Fi presence-based sleep (optional, additive to Task 11)

Built first among the two presence options per the brief (no extra hardware). PIR
sensor support is deferred to v2 per the spec and is not part of this plan.

**Files:**
- Create: `apps/kitchen-kiosk/backend/presence.py`
- Create: `apps/kitchen-kiosk/backend/tests/test_presence.py`
- Modify: `apps/kitchen-kiosk/backend/app.py`
- Modify: `.env.example`
- Modify: `docker-compose.kiosk.yml`

**Interfaces:**
- Consumes: `KIOSK_PRESENCE_KNOWN_MACS` (comma-separated MAC addresses of known phones) and `KIOSK_PRESENCE_METHOD` (`arp` only for v1) env vars.
- Produces: `GET /api/presence` → `{"anyone_home": bool}`. Task 11's frontend schedule check additionally sleeps whenever `anyone_home` is false, on top of the time window.

- [ ] **Step 1: Write the failing tests**

```python
# apps/kitchen-kiosk/backend/tests/test_presence.py
ARP_OUTPUT = """? (192.168.1.10) at aa:bb:cc:dd:ee:01 [ether] on eth0
? (192.168.1.11) at aa:bb:cc:dd:ee:02 [ether] on eth0
"""


def test_presence_true_when_known_mac_present(client, mocker):
    mocker.patch('presence.KNOWN_MACS', ['aa:bb:cc:dd:ee:01'])
    mocker.patch('presence._run_arp_scan', return_value=ARP_OUTPUT)

    response = client.get('/api/presence')

    assert response.status_code == 200
    assert response.get_json() == {'anyone_home': True}


def test_presence_false_when_no_known_mac_present(client, mocker):
    mocker.patch('presence.KNOWN_MACS', ['aa:bb:cc:dd:ee:99'])
    mocker.patch('presence._run_arp_scan', return_value=ARP_OUTPUT)

    response = client.get('/api/presence')

    assert response.get_json() == {'anyone_home': False}


def test_presence_defaults_to_home_when_unconfigured(client, mocker):
    # No MACs configured means presence detection is off - never force sleep.
    mocker.patch('presence.KNOWN_MACS', [])

    response = client.get('/api/presence')

    assert response.get_json() == {'anyone_home': True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_presence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'presence'`

- [ ] **Step 3: Write the presence blueprint**

```python
# apps/kitchen-kiosk/backend/presence.py
"""Wi-Fi presence detection via ARP scan of the local subnet - checks
whether any known phone MAC is currently associated with the network."""
import os
import subprocess

from flask import Blueprint, jsonify

presence_bp = Blueprint('presence', __name__)

KNOWN_MACS = [m.strip().lower() for m in os.getenv('KIOSK_PRESENCE_KNOWN_MACS', '').split(',') if m.strip()]


def _run_arp_scan():
    # Requires net-tools' arp-scan or equivalent to be available in the
    # container/host network; run against the whole local subnet.
    result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
    return result.stdout


@presence_bp.route('/api/presence')
def presence():
    if not KNOWN_MACS:
        # Presence detection is opt-in; unconfigured means never force sleep.
        return jsonify({'anyone_home': True})

    output = _run_arp_scan().lower()
    anyone_home = any(mac in output for mac in KNOWN_MACS)
    return jsonify({'anyone_home': anyone_home})
```

- [ ] **Step 4: Register the blueprint**

In `apps/kitchen-kiosk/backend/app.py`, add:

```python
    from presence import presence_bp
    app.register_blueprint(presence_bp)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/kitchen-kiosk/backend && python -m pytest tests/test_presence.py -v`
Expected: PASS

- [ ] **Step 6: Add env vars and network mode**

Append to `.env.example`:

```
# Wi-Fi presence detection (optional) - comma-separated MAC addresses of known
# phones; when set, the kiosk also sleeps whenever none of them are on the network
KIOSK_PRESENCE_KNOWN_MACS=
```

In `docker-compose.kiosk.yml`, add to `kiosk-api`'s `environment:` block:

```yaml
      KIOSK_PRESENCE_KNOWN_MACS: ${KIOSK_PRESENCE_KNOWN_MACS:-}
```

ARP scanning needs visibility into the host's network/ARP table, which the
default bridge network doesn't provide. Add to the `kiosk-api` service definition
(replacing its `networks:` entry):

```yaml
    network_mode: "host"
```

> Note: `network_mode: host` conflicts with the `networks:` key and with the
> published Traefik labels' internal Docker networking assumption (Traefik
> reaches services by container name on the `homeserver` network). Confirm during
> implementation whether `arp -a` inside the container can see the host's ARP
> table without host networking (some Docker setups expose it via a read-only
> mount of `/proc/net/arp` instead) — if so, prefer that over `network_mode: host`
> to keep Traefik routing intact. This is a deployment detail to verify against
> the actual server, not a design change.

- [ ] **Step 7: Wire presence into the frontend sleep check**

Update `checkSleepSchedule` in `app.js`:

```javascript
  async function checkSleepSchedule() {
    let anyoneHome = true;
    try {
      const presence = await fetch('/api/presence').then(r => r.json());
      anyoneHome = presence.anyone_home;
    } catch (e) {
      console.error('presence check failed, assuming home', e);
    }

    if (isWithinSleepWindow(new Date()) || !anyoneHome) {
      enterSleep();
    } else if (isSleeping) {
      wake();
    }
  }
```

- [ ] **Step 8: Validate and manually verify**

Run: `make validate`

With `KIOSK_PRESENCE_KNOWN_MACS` set to a phone's real MAC, confirm `/api/presence`
returns `true` while that phone is on Wi-Fi and `false` shortly after it
disconnects (e.g. airplane mode), and that the kiosk sleeps accordingly outside
the configured time window too.

- [ ] **Step 9: Commit**

```bash
git add apps/kitchen-kiosk/backend/presence.py apps/kitchen-kiosk/backend/tests/test_presence.py apps/kitchen-kiosk/backend/app.py apps/kitchen-kiosk/frontend/app.js .env.example docker-compose.kiosk.yml
git commit -m "feat: add Wi-Fi presence detection to trigger sleep when nobody's home"
```

---

## Post-plan manual verification (not automatable — do before considering this done)

- Reboot the server; confirm `kiosk-api` and `kiosk-web` come back up healthy
  without manual intervention (`docker compose ps` shows both `Up`).
- Reboot the iPad with the kiosk web app added to the Home Screen and Guided
  Access enabled; confirm it relaunches into the kiosk view and reconnects.
- Set "Auto-Lock: Never" on the iPad (Settings > Display & Brightness) so iOS
  itself never sleeps the screen outside the app's own scheduled sleep window.
- `make test-domain-access` against `kiosk.${DOMAIN}` and `kiosk-api.${DOMAIN}`.
