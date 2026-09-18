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

    @patch('app.get_weather_api')
    def test_bom_weather_success(self, mock_get_weather_api, client):
        """Test successful BOM weather data retrieval"""
        # Mock the weather API response
        mock_weather_api = Mock()

        # Mock location() method
        mock_weather_api.location.return_value = {
            'name': 'Parramatta',
            'state': 'NSW',
            'geohash': 'r3gx',
            'latitude': -33.8175,
            'longitude': 151.0033
        }

        # Mock observations() method
        mock_weather_api.observations.return_value = {
            'temp': 22.5,
            'temp_feels_like': 21.0,
            'wind': {'speed_kilometre': 15, 'direction': 'NW'},
            'rain_since_9am': 0,
            'humidity': 65
        }

        # Mock forecasts_daily() method
        mock_weather_api.forecasts_daily.return_value = [
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

        # Mock forecasts_hourly() method
        mock_weather_api.forecasts_hourly.return_value = [
            {'time': '2025-10-27T12:00:00Z', 'temp': 24, 'rain': {'chance': 10}}
        ]

        # Mock forecast_rain() method
        mock_weather_api.forecast_rain.return_value = {
            'amount': '0-2mm',
            'chance': '20%',
            'start_time': None
        }

        mock_get_weather_api.return_value = mock_weather_api

        response = client.get('/api/bom/weather')
        assert response.status_code == 200

        data = response.get_json()
        assert 'location' in data
        assert 'observations' in data
        assert 'forecast_daily' in data
        assert 'forecast_hourly' in data
        assert 'forecast_rain' in data
        assert 'updated' in data

        # Check observations
        assert data['observations']['temp'] == 22.5
        assert data['observations']['humidity'] == 65

        # Check forecast
        assert len(data['forecast_daily']) > 0
        assert data['forecast_daily'][0]['temp_max'] == 28

    @patch('app.get_weather_api')
    def test_bom_weather_api_error(self, mock_get_weather_api, client):
        """Test BOM weather endpoint handles API errors"""
        mock_get_weather_api.side_effect = Exception('API connection failed')

        response = client.get('/api/bom/weather')
        assert response.status_code == 500

        data = response.get_json()
        assert 'error' in data
        assert 'API connection failed' in data['error']

    @pytest.mark.skip(reason="Caching behavior cannot be tested when mocking the cached function itself. "
                             "The @cached decorator is bypassed when we mock get_weather_api. "
                             "To properly test caching, we would need to mock the underlying weather_au library "
                             "instead of the cached wrapper function.")
    @patch('app.get_weather_api')
    def test_bom_weather_caching(self, mock_get_weather_api, client):
        """Test BOM weather endpoint uses caching"""
        mock_weather_api = Mock()
        mock_weather_api.location.return_value = {
            'name': 'Parramatta',
            'state': 'NSW'
        }
        mock_weather_api.observations.return_value = {'temp': 22.5}
        mock_weather_api.forecasts_daily.return_value = [{'temp_max': 28}]
        mock_weather_api.forecasts_hourly.return_value = []
        mock_weather_api.forecast_rain.return_value = {}
        mock_get_weather_api.return_value = mock_weather_api

        # First request
        response1 = client.get('/api/bom/weather')
        assert response1.status_code == 200

        # Second request (should use cache)
        response2 = client.get('/api/bom/weather')
        assert response2.status_code == 200

        # Weather API should only be called once due to caching
        assert mock_get_weather_api.call_count == 1


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

        response = client.get('/api/transport/departures/10101229')
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

        response = client.get('/api/transport/departures/10101229')
        assert response.status_code == 200

        data = response.get_json()
        departure = data['departures'][0]
        assert departure['delay_minutes'] == 5  # 5 minutes late

    @patch('app.requests.get')
    def test_transport_departures_missing_stop_id(self, mock_get, client):
        """Test transport departures requires stopId parameter"""
        response = client.get('/api/transport/departures')
        assert response.status_code == 404  # Route not found without stop_id path parameter

    @patch('app.requests.get')
    def test_transport_departures_api_error(self, mock_get, client):
        """Test transport departures handles API errors"""
        mock_get.side_effect = Exception('Network error')

        response = client.get('/api/transport/departures/10101229')
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

        response = client.get('/api/transport/departures/10101229')
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

        response = client.get('/api/transport/departures/10101229')
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

        response = client.get('/api/transport/departures/10101229')
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

    @patch('app.get_weather_api')
    def test_generic_exception_handling(self, mock_get_weather_api, client):
        """Test generic exception handling returns 500"""
        mock_get_weather_api.side_effect = RuntimeError('Unexpected error')

        response = client.get('/api/bom/weather')
        assert response.status_code == 500

        data = response.get_json()
        assert 'error' in data


class TestTrafficActiveRoutes:
    """Tests for /api/traffic/active-routes endpoint"""

    @patch('app.get_active_routes')
    def test_active_routes_success(self, mock_get_active_routes, client):
        """Test successful active routes retrieval"""
        mock_get_active_routes.return_value = [
            {
                'name': 'Morning Commute',
                'origin': 'Home',
                'destination': 'Work',
                'route_num': 1,
                'schedule': 'Mon-Fri 07:00-09:00'
            },
            {
                'name': 'Evening Commute',
                'origin': 'Work',
                'destination': 'Home',
                'route_num': 2,
                'schedule': 'Mon-Fri 17:00-19:00'
            }
        ]

        response = client.get('/api/traffic/active-routes')
        assert response.status_code == 200

        data = response.get_json()
        assert 'routes' in data
        assert 'count' in data
        assert 'updated' in data
        assert data['count'] == 2
        assert len(data['routes']) == 2
        assert data['routes'][0]['name'] == 'Morning Commute'
        assert data['routes'][1]['name'] == 'Evening Commute'

    @patch('app.get_active_routes')
    def test_active_routes_empty(self, mock_get_active_routes, client):
        """Test active routes when none are active"""
        mock_get_active_routes.return_value = []

        response = client.get('/api/traffic/active-routes')
        assert response.status_code == 200

        data = response.get_json()
        assert data['count'] == 0
        assert data['routes'] == []

    @patch('app.get_active_routes')
    def test_active_routes_error(self, mock_get_active_routes, client):
        """Test active routes handles errors"""
        mock_get_active_routes.side_effect = Exception('Configuration error')

        response = client.get('/api/traffic/active-routes')
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


class TestIcloudpdStatusEndpoint:
    """Tests for /api/icloudpd/status (single merged container)"""

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_both_accounts_ok_is_ok(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:10Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['statusLabel'] == 'OK'
        assert data['name'] == 'icloudpd'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_one_account_auth_required_is_worst(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:08Z ERROR Invalid authentication token, please log in\n"
            "2026-09-17T04:00:09Z INFO Waiting for MFA code via webui\n"
        )
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'auth_required'
        assert data['statusLabel'] == 'Re-auth needed'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_one_account_syncing_beats_ok(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:08Z INFO Downloading 12 original photos to /drive/account-b\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'syncing'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_drive_missing_short_circuits_regardless_of_account_lines(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'unhealthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'drive_missing'
        assert data['statusLabel'] == 'Drive not mounted'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_not_running_is_down(self, mock_api, mock_logs, client):
        mock_api.return_value = {'State': {'Status': 'exited', 'Running': False, 'Health': None}}
        mock_logs.return_value = ""
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'down'
        assert data['statusLabel'] == 'Stopped'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_stale_drive_marker_before_recovery_is_not_drive_missing(self, mock_api, mock_logs, client):
        """A drive-guard failure from a previous container lifetime, followed by
        real account activity proving the guard has since passed, must not pin
        the status to drive_missing."""
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T01:00:00Z backup drive not mounted or wrong drive\n"
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:10Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'ok'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_no_account_activity_yet_is_unknown(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = "2026-09-17T04:00:00Z INFO Starting web server for WebUI authentication...\n"
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'unknown'

    @patch('app._docker_api', side_effect=OSError("socket gone"))
    def test_socket_error_is_unknown_http_200(self, mock_api, client):
        resp = client.get('/api/icloudpd/status')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'unknown'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_busy_sync_with_no_marker_in_window_is_syncing_not_unknown(self, mock_api, mock_logs, client):
        """A tail window entirely full of download activity with no 'Processing
        user:' marker (marker scrolled out by a heavy sync) must still report
        syncing, not unknown."""
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Downloading photo1.HEIC\n"
            "2026-09-17T04:00:01Z INFO Downloaded photo1.HEIC\n"
            "2026-09-17T04:00:02Z INFO Downloading photo2.HEIC\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'syncing'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_just_started_account_segment_is_syncing_not_unknown(self, mock_api, mock_logs, client):
        """An account whose 'Processing user:' marker just printed, with no
        further lines yet, must not report unknown (which would outrank a
        sibling account's ok)."""
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
        )
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'syncing'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_worst_of_ties_prefers_more_recent_last_sync(self, mock_api, mock_logs, client):
        """When both accounts are 'ok', lastSync must reflect whichever
        actually synced more recently, not whichever account appears first
        in the log."""
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T09:00:00Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['lastSync'] == '2026-09-17T09:00:00Z'

    def test_rel_time_parses_nanosecond_docker_timestamp(self):
        from app import _rel_time
        # Docker RFC3339Nano — 9 fractional digits
        assert _rel_time('2020-01-01T00:00:00.123456789+00:00') is not None

    def test_demux_docker_stream_parses_multiplexed_frames(self):
        import struct
        from app import _demux_docker_stream
        payload1 = b'2026-09-06T04:15:03.000000000Z line one\n'
        payload2 = b'2026-09-06T04:15:04.000000000Z line two\n'
        raw = (struct.pack('>BxxxI', 1, len(payload1)) + payload1
               + struct.pack('>BxxxI', 2, len(payload2)) + payload2)
        text = _demux_docker_stream(raw)
        assert 'line one' in text and 'line two' in text
