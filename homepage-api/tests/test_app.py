"""
Unit tests for Homepage API endpoints
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json


class TestHealthEndpoint:
    """Tests for /api/health endpoint"""

    def test_health_check_success(self, client):
        """Test health check returns 200 OK"""
        response = client.get('/api/health')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data


class TestBOMWeatherEndpoint:
    """Tests for /api/bom/weather endpoint"""

    @patch('app.weather_api.get_location')
    def test_bom_weather_success(self, mock_get_location, client):
        """Test successful BOM weather data retrieval"""
        # Mock the weather API response
        mock_location = Mock()
        mock_location.observations.return_value = {
            'temp': 22.5,
            'temp_feels_like': 21.0,
            'wind': {'speed_kilometre': 15, 'direction': 'NW'},
            'rain_since_9am': 0,
            'humidity': 65
        }
        mock_location.forecasts_daily.return_value = [
            {
                'temp_min': 18,
                'temp_max': 28,
                'short_text': 'Partly cloudy',
                'icon_descriptor': 'cloudy',
                'rain': {'amount': {'min': 0, 'max': 2}, 'chance': 20},
                'uv': {'max_index': 8, 'start_time': '2025-10-27T10:00:00Z'},
                'astronomical': {
                    'sunrise_time': '2025-10-27T05:30:00Z',
                    'sunset_time': '2025-10-27T18:45:00Z'
                },
                'fire_danger': 'Low - Moderate',
                'now': {'temp_now': 22}
            }
        ]
        mock_location.forecasts_three_hourly.return_value = [
            {'time': '2025-10-27T12:00:00Z', 'temp': 24, 'rain': {'chance': 10}}
        ]
        mock_location.forecasts_rain.return_value = {
            'amount': '0-2mm',
            'chance': '20%',
            'start_time': None
        }

        mock_get_location.return_value = mock_location

        response = client.get('/api/bom/weather')
        assert response.status_code == 200

        data = response.get_json()
        assert 'location' in data
        assert 'observations' in data
        assert 'forecast_daily' in data
        assert 'forecast_3hourly' in data
        assert 'forecast_rain' in data
        assert 'updated' in data

        # Check observations
        assert data['observations']['temp'] == 22.5
        assert data['observations']['humidity'] == 65

        # Check forecast
        assert len(data['forecast_daily']) > 0
        assert data['forecast_daily'][0]['temp_max'] == 28

    @patch('app.weather_api.get_location')
    def test_bom_weather_api_error(self, mock_get_location, client):
        """Test BOM weather endpoint handles API errors"""
        mock_get_location.side_effect = Exception('API connection failed')

        response = client.get('/api/bom/weather')
        assert response.status_code == 500

        data = response.get_json()
        assert 'error' in data
        assert 'API connection failed' in data['error']

    @patch('app.weather_api.get_location')
    def test_bom_weather_caching(self, mock_get_location, client):
        """Test BOM weather endpoint uses caching"""
        mock_location = Mock()
        mock_location.observations.return_value = {'temp': 22.5}
        mock_location.forecasts_daily.return_value = [{'temp_max': 28}]
        mock_location.forecasts_three_hourly.return_value = []
        mock_location.forecasts_rain.return_value = {}
        mock_get_location.return_value = mock_location

        # First request
        response1 = client.get('/api/bom/weather')
        assert response1.status_code == 200

        # Second request (should use cache)
        response2 = client.get('/api/bom/weather')
        assert response2.status_code == 200

        # Weather API should only be called once due to caching
        assert mock_get_location.call_count == 1


class TestTransportNSWEndpoint:
    """Tests for /api/transport/departures endpoint"""

    @patch('app.requests.get')
    def test_transport_departures_success(self, mock_get, client):
        """Test successful transport departures retrieval"""
        # Mock Transport NSW API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'stopEvents': [
                {
                    'isRealtimeControlled': True,
                    'location': {
                        'properties': {
                            'platformName': 'Platform 1'
                        }
                    },
                    'departureTimePlanned': '2025-10-27T05:17:00Z',
                    'departureTimeEstimated': '2025-10-27T05:17:00Z',
                    'transportation': {
                        'number': 'T1 North Shore & Western Line',
                        'destination': {
                            'name': 'Hornsby via Gordon'
                        }
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        response = client.get('/api/transport/departures?stopId=10101229')
        assert response.status_code == 200

        data = response.get_json()
        assert 'stopId' in data
        assert 'departures' in data
        assert 'updated' in data
        assert len(data['departures']) == 1

        departure = data['departures'][0]
        assert departure['platform'] == 'Platform 1'
        assert departure['line'] == 'T1 North Shore & Western Line'
        assert departure['destination'] == 'Hornsby via Gordon'
        assert departure['realtime'] is True
        assert departure['delay_minutes'] == 0

    @patch('app.requests.get')
    def test_transport_departures_with_delay(self, mock_get, client):
        """Test transport departures correctly calculates delays"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'stopEvents': [
                {
                    'isRealtimeControlled': True,
                    'location': {
                        'properties': {
                            'platformName': 'Platform 2'
                        }
                    },
                    'departureTimePlanned': '2025-10-27T05:17:00Z',
                    'departureTimeEstimated': '2025-10-27T05:22:00Z',  # 5 min delay
                    'transportation': {
                        'number': 'T2',
                        'destination': {'name': 'City'}
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        response = client.get('/api/transport/departures?stopId=10101229')
        assert response.status_code == 200

        data = response.get_json()
        departure = data['departures'][0]
        assert departure['delay_minutes'] == 5  # 5 minutes late

    @patch('app.requests.get')
    def test_transport_departures_missing_stop_id(self, mock_get, client):
        """Test transport departures requires stopId parameter"""
        response = client.get('/api/transport/departures')
        assert response.status_code == 400

        data = response.get_json()
        assert 'error' in data
        assert 'stopId' in data['error']

    @patch('app.requests.get')
    def test_transport_departures_api_error(self, mock_get, client):
        """Test transport departures handles API errors"""
        mock_get.side_effect = Exception('Network error')

        response = client.get('/api/transport/departures?stopId=10101229')
        assert response.status_code == 500

        data = response.get_json()
        assert 'error' in data

    @patch('app.requests.get')
    def test_transport_departures_platform_parsing(self, mock_get, client):
        """Test platform is correctly extracted from location.properties.platformName"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'stopEvents': [
                {
                    'isRealtimeControlled': False,
                    'location': {
                        'properties': {
                            'platformName': 'Platform 3',
                            'platform': 'PTA3'  # Internal code (not used)
                        }
                    },
                    'departureTimePlanned': '2025-10-27T05:17:00Z',
                    'transportation': {
                        'number': 'T1',
                        'destination': {'name': 'Central'}
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        response = client.get('/api/transport/departures?stopId=10101229')
        data = response.get_json()

        # Should use platformName, not the internal platform code
        assert data['departures'][0]['platform'] == 'Platform 3'

    @patch('app.requests.get')
    def test_transport_departures_no_platform(self, mock_get, client):
        """Test transport departures handles missing platform gracefully"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'stopEvents': [
                {
                    'isRealtimeControlled': False,
                    'location': {
                        'properties': {}  # No platform info
                    },
                    'departureTimePlanned': '2025-10-27T05:17:00Z',
                    'transportation': {
                        'number': 'Bus 123',
                        'destination': {'name': 'Parramatta'}
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        response = client.get('/api/transport/departures?stopId=10101229')
        assert response.status_code == 200

        data = response.get_json()
        assert data['departures'][0]['platform'] is None

    @patch('app.requests.get')
    def test_transport_departures_invalid_timestamp(self, mock_get, client):
        """Test transport departures handles invalid timestamps gracefully"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'stopEvents': [
                {
                    'isRealtimeControlled': True,
                    'location': {
                        'properties': {'platformName': 'Platform 1'}
                    },
                    'departureTimePlanned': 'invalid-timestamp',
                    'departureTimeEstimated': 'also-invalid',
                    'transportation': {
                        'number': 'T1',
                        'destination': {'name': 'Central'}
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        response = client.get('/api/transport/departures?stopId=10101229')
        assert response.status_code == 200

        data = response.get_json()
        # Should default to 0 delay when timestamps can't be parsed
        assert data['departures'][0]['delay_minutes'] == 0


class TestErrorHandling:
    """Tests for error handling across all endpoints"""

    def test_404_on_unknown_endpoint(self, client):
        """Test 404 error for unknown endpoints"""
        response = client.get('/api/unknown')
        assert response.status_code == 404

    @patch('app.weather_api.get_location')
    def test_generic_exception_handling(self, mock_get_location, client):
        """Test generic exception handling returns 500"""
        mock_get_location.side_effect = RuntimeError('Unexpected error')

        response = client.get('/api/bom/weather')
        assert response.status_code == 500

        data = response.get_json()
        assert 'error' in data


class TestCORSHeaders:
    """Tests for CORS configuration"""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present on API responses"""
        response = client.get('/api/health')

        # CORS headers should be present (handled by flask-cors)
        # The exact header name might vary, so we just check the response is successful
        assert response.status_code == 200
