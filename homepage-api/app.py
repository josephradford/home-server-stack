"""
Homepage Dashboard Backend API
Provides custom endpoints for:
- BOM weather data (Australian Bureau of Meteorology)
- Transport NSW data enrichment
- Traffic conditions (TomTom API)
- Home Assistant integration helpers
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import os
import json
from functools import lru_cache, wraps
from weather_au import api as weather_api
from traffic_scheduler import get_active_routes, is_route_active

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
TRANSPORT_NSW_API_KEY = os.getenv('TRANSPORT_NSW_API_KEY')
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY')

# BOM Weather Configuration (using weather-au library)
# Location search string - suburb name only (e.g., "parramatta", "sydney")
BOM_LOCATION = os.getenv('BOM_LOCATION', 'parramatta')


@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'transport_nsw': 'configured' if TRANSPORT_NSW_API_KEY else 'not configured',
            'tomtom': 'configured' if TOMTOM_API_KEY else 'not configured',
            'wireguard': 'system service',
            'docker': 'system service'
        }
    })


# =============================================================================
# BOM WEATHER (using weather-au library)
# =============================================================================

# Cache decorator with time-based expiry
def timed_lru_cache(seconds: int, maxsize: int = 128):
    """LRU cache with time-based expiry"""
    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.utcnow() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.utcnow() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime
            return func(*args, **kwargs)

        wrapped_func.cache_clear = func.cache_clear
        return wrapped_func
    return wrapper_cache


@timed_lru_cache(seconds=300, maxsize=1)  # Cache for 5 minutes
def get_weather_api(location):
    """
    Get weather API instance for a location
    Cached to avoid repeated API calls
    """
    return weather_api.WeatherApi(search=location, debug=0)


@app.route('/api/bom/weather')
def bom_weather():
    """
    Fetch comprehensive weather data from Australian BOM using weather-au library

    Returns:
        - Current observations (temperature, feels like, wind, rain, humidity)
        - 7-day daily forecast (temps, rain chance/amount, UV, sunrise/sunset, fire danger)
        - Hourly forecast (detailed hourly conditions)
        - Next rain forecast (if available)

    Uses BOM's official API via weather-au library for accurate, comprehensive data
    Cached for 5 minutes to respect BOM servers
    """
    try:
        # Get weather API instance
        w = get_weather_api(BOM_LOCATION)

        # Get location info
        location_data = w.location()
        if not location_data:
            return jsonify({'error': f'Location "{BOM_LOCATION}" not found'}), 404

        # Get current observations
        try:
            observations = w.observations()
        except Exception:
            observations = None

        # Get daily forecasts
        try:
            forecasts_daily = w.forecasts_daily()
        except Exception:
            forecasts_daily = None

        # Get hourly forecasts
        try:
            forecasts_hourly = w.forecasts_hourly()
        except Exception:
            # Some locations don't have hourly forecasts available
            forecasts_hourly = None

        # Get rain forecast
        try:
            forecast_rain = w.forecast_rain()
        except Exception:
            forecast_rain = None

        # Build comprehensive response
        weather_data = {
            'location': {
                'name': location_data.get('name'),
                'state': location_data.get('state'),
                'geohash': location_data.get('geohash'),
                'latitude': location_data.get('latitude'),
                'longitude': location_data.get('longitude')
            },
            'observations': None,
            'forecast_daily': None,
            'forecast_hourly': None,
            'forecast_rain': None,
            'updated': datetime.now().isoformat()
        }

        # Process observations
        if observations:
            weather_data['observations'] = {
                'temp': observations.get('temp'),
                'temp_feels_like': observations.get('temp_feels_like'),
                'rain_since_9am': observations.get('rain_since_9am'),
                'humidity': observations.get('humidity'),
                'wind': {
                    'speed_kmh': observations.get('wind', {}).get('speed_kilometre'),
                    'speed_knot': observations.get('wind', {}).get('speed_knot'),
                    'direction': observations.get('wind', {}).get('direction')
                },
                'station': {
                    'bom_id': observations.get('station', {}).get('bom_id'),
                    'name': observations.get('station', {}).get('name'),
                    'distance_m': observations.get('station', {}).get('distance')
                }
            }

        # Process daily forecasts
        if forecasts_daily:
            weather_data['forecast_daily'] = []
            for day in forecasts_daily:
                rain_data = day.get('rain', {})
                rain_amount = rain_data.get('amount', {}) if rain_data else {}
                uv_data = day.get('uv', {})
                astro_data = day.get('astronomical', {})
                now_data = day.get('now', {})

                forecast_day = {
                    'date': day.get('date'),
                    'temp_min': day.get('temp_min'),
                    'temp_max': day.get('temp_max'),
                    'extended_text': day.get('extended_text'),
                    'short_text': day.get('short_text'),
                    'icon_descriptor': day.get('icon_descriptor'),
                    'rain': {
                        'chance': rain_data.get('chance') if rain_data else None,
                        'amount_min': rain_amount.get('min') if rain_amount else None,
                        'amount_max': rain_amount.get('max') if rain_amount else None,
                        'amount_units': rain_amount.get('units') if rain_amount else None
                    },
                    'uv': {
                        'category': uv_data.get('category') if uv_data else None,
                        'max_index': uv_data.get('max_index') if uv_data else None,
                        'start_time': uv_data.get('start_time') if uv_data else None,
                        'end_time': uv_data.get('end_time') if uv_data else None
                    },
                    'astronomical': {
                        'sunrise_time': astro_data.get('sunrise_time') if astro_data else None,
                        'sunset_time': astro_data.get('sunset_time') if astro_data else None
                    },
                    'fire_danger': day.get('fire_danger'),
                    'now': {
                        'is_night': now_data.get('is_night') if now_data else None,
                        'now_label': now_data.get('now_label') if now_data else None,
                        'temp_now': now_data.get('temp_now') if now_data else None,
                        'later_label': now_data.get('later_label') if now_data else None,
                        'temp_later': now_data.get('temp_later') if now_data else None
                    }
                }
                weather_data['forecast_daily'].append(forecast_day)

        # Process hourly forecasts
        if forecasts_hourly:
            weather_data['forecast_hourly'] = []
            for period in forecasts_hourly:
                rain_data = period.get('rain', {})
                rain_amount = rain_data.get('amount', {}) if rain_data else {}
                wind_data = period.get('wind', {})

                forecast_3h = {
                    'time': period.get('time'),
                    'temp': period.get('temp'),
                    'icon_descriptor': period.get('icon_descriptor'),
                    'is_night': period.get('is_night'),
                    'next_forecast_period': period.get('next_forecast_period'),
                    'rain': {
                        'chance': rain_data.get('chance') if rain_data else None,
                        'amount_min': rain_amount.get('min') if rain_amount else None,
                        'amount_max': rain_amount.get('max') if rain_amount else None,
                        'amount_units': rain_amount.get('units') if rain_amount else None
                    },
                    'wind': {
                        'speed_kmh': wind_data.get('speed_kilometre') if wind_data else None,
                        'speed_knot': wind_data.get('speed_knot') if wind_data else None,
                        'direction': wind_data.get('direction') if wind_data else None
                    }
                }
                weather_data['forecast_hourly'].append(forecast_3h)

        # Process rain forecast
        if forecast_rain:
            weather_data['forecast_rain'] = {
                'amount': forecast_rain.get('amount'),
                'chance': forecast_rain.get('chance'),
                'start_time': forecast_rain.get('start_time'),
                'period': forecast_rain.get('period')
            }

        return jsonify(weather_data)

    except Exception as e:
        return jsonify({'error': f'Failed to fetch BOM weather data: {str(e)}'}), 500


# =============================================================================
# TRANSPORT NSW
# =============================================================================

@app.route('/api/transport/departures/<stop_id>')
def transport_departures(stop_id):
    """
    Get Transport NSW departures with enhanced data
    """
    try:
        if not TRANSPORT_NSW_API_KEY:
            return jsonify({'error': 'Transport NSW API key not configured'}), 503

        url = 'https://api.transport.nsw.gov.au/v1/tp/departure_mon'
        params = {
            'outputFormat': 'rapidJSON',
            'coordOutputFormat': 'EPSG:4326',
            'mode': 'direct',
            'type_dm': 'stop',
            'name_dm': stop_id,
            'departureMonitorMacro': 'true',
            'TfNSWDM': 'true',
            'version': '10.2.1.42'
        }

        headers = {
            'Authorization': f'apikey {TRANSPORT_NSW_API_KEY}'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Parse and simplify the response
        departures = []
        stop_events = data.get('stopEvents', [])

        for event in stop_events[:5]:  # Get next 5 departures
            transportation = event.get('transportation', {})
            location = event.get('location', {})

            # Calculate delay if realtime data is available
            delay_minutes = 0
            if event.get('isRealtimeControlled'):
                try:
                    planned_str = event.get('departureTimePlanned')
                    estimated_str = event.get('departureTimeEstimated')
                    if planned_str and estimated_str:
                        # Parse ISO timestamps
                        planned = datetime.fromisoformat(planned_str.replace('Z', '+00:00'))
                        estimated = datetime.fromisoformat(estimated_str.replace('Z', '+00:00'))
                        # Calculate difference in minutes
                        delay_minutes = int((estimated - planned).total_seconds() / 60)
                except (ValueError, AttributeError):
                    # If parsing fails, default to 0
                    delay_minutes = 0

            departures.append({
                'time': event.get('departureTimePlanned'),
                'destination': transportation.get('destination', {}).get('name'),
                'line': transportation.get('number'),
                'platform': location.get('properties', {}).get('platformName'),
                'realtime': event.get('isRealtimeControlled', False),
                'delay_minutes': delay_minutes
            })

        return jsonify({
            'stopId': stop_id,
            'departures': departures,
            'updated': datetime.now().isoformat()
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Transport API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# TRAFFIC CONDITIONS
# =============================================================================

@app.route('/api/traffic/route')
def traffic_route():
    """
    Get traffic conditions for a route using TomTom API
    Query params: origin, destination (full addresses)
    """
    try:
        if not TOMTOM_API_KEY:
            return jsonify({'error': 'TomTom API key not configured'}), 503

        origin = request.args.get('origin')
        destination = request.args.get('destination')

        if not origin or not destination:
            return jsonify({'error': 'origin and destination required'}), 400

        # Geocode addresses to coordinates
        origin_coords = geocode_address(origin)
        destination_coords = geocode_address(destination)

        if not origin_coords or not destination_coords:
            return jsonify({'error': 'Could not geocode addresses'}), 400

        # Get route with traffic
        route_url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_coords}:{destination_coords}/json"
        params = {
            'key': TOMTOM_API_KEY,
            'traffic': 'true',
            'travelMode': 'car'
        }

        response = requests.get(route_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'routes' in data and len(data['routes']) > 0:
            route = data['routes'][0]['summary']

            traffic_delay = route.get('trafficDelayInSeconds', 0)
            travel_time_minutes = route.get('travelTimeInSeconds', 0) / 60

            return jsonify({
                'origin': origin,
                'destination': destination,
                'travelTimeMinutes': round(travel_time_minutes),
                'trafficDelayMinutes': round(traffic_delay / 60),
                'distanceKm': round(route.get('lengthInMeters', 0) / 1000, 1),
                'status': 'heavy' if traffic_delay > 600 else 'moderate' if traffic_delay > 300 else 'clear',
                'updated': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'No route found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def geocode_address(address):
    """Helper function to geocode an address using TomTom"""
    try:
        url = 'https://api.tomtom.com/search/2/geocode/' + requests.utils.quote(address) + '.json'
        params = {
            'key': TOMTOM_API_KEY,
            'countrySet': 'AU',  # Limit to Australia
            'limit': 1
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('results'):
            position = data['results'][0]['position']
            return f"{position['lat']},{position['lon']}"

        return None
    except:
        return None


@app.route('/api/traffic/active-routes')
def active_routes():
    """
    Get list of currently active traffic routes based on schedule

    Returns routes that are active based on their configured schedule
    (e.g., morning commute only shows 7-9am on weekdays)

    Example response:
    {
        "routes": [
            {
                "name": "Morning Commute",
                "origin": "123 Home St, Parramatta NSW",
                "destination": "456 Work St, Sydney NSW",
                "route_num": 1,
                "schedule": "Mon-Fri 07:00-09:00"
            }
        ],
        "count": 1,
        "updated": "2025-10-27T08:30:00.123456"
    }
    """
    try:
        routes = get_active_routes()
        return jsonify({
            'routes': routes,
            'count': len(routes),
            'updated': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# WIREGUARD VPN STATUS
# =============================================================================

@app.route('/api/wireguard/status')
def wireguard_status():
    """
    Get WireGuard VPN status from system service
    Returns interface status, connected peers, and basic stats
    """
    try:
        import subprocess
        
        # Check if WireGuard service is running
        try:
            service_result = subprocess.run(
                ['systemctl', 'is-active', 'wg-quick@wg0'],
                capture_output=True,
                text=True,
                timeout=5
            )
            service_status = service_result.stdout.strip()
            service_running = service_status == 'active'
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Service check timed out'}), 500
        except Exception:
            service_running = False
            service_status = 'unknown'
        
        if not service_running:
            return jsonify({
                'status': f'Inactive ({service_status})',
                'peers': 0,
                'interface': 'wg0 (down)',
                'service_status': service_status,
                'updated': datetime.now().isoformat()
            })
        
        # Get WireGuard interface details
        try:
            wg_result = subprocess.run(
                ['wg', 'show', 'wg0'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if wg_result.returncode != 0:
                return jsonify({
                    'status': 'Error',
                    'peers': 0,
                    'interface': 'wg0 (error)',
                    'error': 'Failed to query WireGuard interface',
                    'updated': datetime.now().isoformat()
                })
            
            wg_output = wg_result.stdout
            
            # Parse output to count peers
            peer_count = 0
            active_peers = 0
            
            lines = wg_output.split('\n')
            for line in lines:
                if line.strip().startswith('peer:'):
                    peer_count += 1
                elif 'latest handshake:' in line.lower():
                    # Check if handshake is recent (within last 5 minutes)
                    if 'minute' in line or 'second' in line:
                        active_peers += 1
            
            status_text = 'Active'
            if peer_count == 0:
                status_text = 'Active (no peers)'
            elif active_peers > 0:
                status_text = f'Active ({active_peers}/{peer_count} connected)'
            else:
                status_text = f'Active ({peer_count} peers configured)'
            
            return jsonify({
                'status': status_text,
                'peers': f'{active_peers}/{peer_count}' if peer_count > 0 else '0',
                'interface': 'wg0 (up)',
                'service_status': 'active',
                'updated': datetime.now().isoformat()
            })
            
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'WireGuard query timed out'}), 500
        except Exception as e:
            return jsonify({
                'status': 'Error',
                'peers': 0,
                'interface': 'wg0 (error)',
                'error': f'Failed to query WireGuard: {str(e)}',
                'updated': datetime.now().isoformat()
            })
    
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


# =============================================================================
# DOCKER DAEMON STATUS
# =============================================================================

@app.route('/api/docker/status')
def docker_status():
    """
    Get Docker daemon status and basic system information
    Returns service status, container counts, and resource info
    """
    try:
        import subprocess
        
        # Check if Docker service is running
        try:
            service_result = subprocess.run(
                ['systemctl', 'is-active', 'docker'],
                capture_output=True,
                text=True,
                timeout=5
            )
            service_status = service_result.stdout.strip()
            service_running = service_status == 'active'
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Service check timed out'}), 500
        except Exception:
            service_running = False
            service_status = 'unknown'
        
        if not service_running:
            return jsonify({
                'status': f'Inactive ({service_status})',
                'containers': 'N/A',
                'version': 'N/A',
                'service_status': service_status,
                'updated': datetime.now().isoformat()
            })
        
        # Get Docker info
        try:
            # Get container counts
            containers_result = subprocess.run(
                ['docker', 'ps', '-q'],
                capture_output=True,
                text=True,
                timeout=10
            )
            running_containers = len([line for line in containers_result.stdout.strip().split('\n') if line])
            
            containers_all_result = subprocess.run(
                ['docker', 'ps', '-aq'],
                capture_output=True,
                text=True,
                timeout=10
            )
            total_containers = len([line for line in containers_all_result.stdout.strip().split('\n') if line])
            
            # Get Docker version
            version_result = subprocess.run(
                ['docker', 'version', '--format', '{{.Server.Version}}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            docker_version = version_result.stdout.strip() if version_result.returncode == 0 else 'Unknown'
            
            # Get basic system stats
            info_result = subprocess.run(
                ['docker', 'system', 'df', '--format', 'table'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Parse docker system df output for basic disk usage
            disk_usage = 'Unknown'
            if info_result.returncode == 0:
                lines = info_result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header
                    # Look for "Images" line which contains total space used
                    for line in lines[1:]:
                        if 'Images' in line:
                            # Extract size (usually 3rd or 4th column)
                            parts = line.split()
                            if len(parts) >= 3:
                                disk_usage = parts[2] if parts[2] != '0B' else parts[3] if len(parts) > 3 else 'Unknown'
                            break
            
            status_text = f'Active ({running_containers} running)'
            if total_containers > running_containers:
                status_text = f'Active ({running_containers}/{total_containers} running)'
            
            return jsonify({
                'status': status_text,
                'containers': f'{running_containers}/{total_containers}',
                'version': f'v{docker_version}',
                'disk_usage': disk_usage,
                'service_status': 'active',
                'updated': datetime.now().isoformat()
            })
            
        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Docker query timed out'}), 500
        except Exception as e:
            return jsonify({
                'status': 'Error',
                'containers': 'N/A',
                'version': 'N/A', 
                'disk_usage': 'N/A',
                'error': f'Failed to query Docker: {str(e)}',
                'updated': datetime.now().isoformat()
            })
    
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


if __name__ == '__main__':
    # Clear weather API cache on startup
    get_weather_api.cache_clear()

    # Run server
    app.run(host='0.0.0.0', port=5200, debug=False)
