import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ['HOMEPAGE_API_URL'] = 'http://homepage-api:5000'
os.environ['KIOSK_CALENDAR_ICAL_URLS'] = 'http://a.example/cal.ics'

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
