import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ['HOMEPAGE_API_URL'] = 'http://homepage-api:5000'
os.environ['KIOSK_CALENDAR_ICAL_URLS'] = 'http://a.example/cal.ics'
os.environ['KIOSK_RECIPES_DIR'] = '/tmp/kiosk-test-recipes'
os.environ['KIOSK_IMMICH_URL'] = 'http://immich-server:2283'
os.environ['KIOSK_IMMICH_API_KEY'] = 'test-immich-key'
os.environ['KIOSK_IMMICH_ALBUM_IDS'] = 'album-1'

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_caches():
    """Module-level TTL caches (calendar_feed, photos) must not leak between
    tests - reset them before every test."""
    import calendar_feed
    import photos
    calendar_feed._events_cache['data'] = None
    calendar_feed._events_cache['fetched_at'] = 0
    photos._assets_cache['data'] = None
    photos._assets_cache['fetched_at'] = 0
    yield
