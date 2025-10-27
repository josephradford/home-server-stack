"""
Pytest configuration and fixtures for Homepage API tests
"""
import pytest
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app


@pytest.fixture
def app():
    """Create Flask app instance for testing"""
    flask_app.config['TESTING'] = True
    flask_app.config['DEBUG'] = False

    # Set test environment variables
    os.environ['BOM_LOCATION'] = 'parramatta'
    os.environ['TRANSPORT_NSW_API_KEY'] = 'test-api-key'
    os.environ['TOMTOM_API_KEY'] = 'test-tomtom-key'
    os.environ['HOMEASSISTANT_URL'] = 'http://test-ha:8123'
    os.environ['HOMEASSISTANT_TOKEN'] = 'test-token'

    yield flask_app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()
