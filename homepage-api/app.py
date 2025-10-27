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

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
TRANSPORT_NSW_API_KEY = os.getenv('TRANSPORT_NSW_API_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJfWHo1V0FvU3VPLUozOTRLSkNucXctX21SU08tdGNvWGhVdDBlekc3SU5zIiwiaWF0IjoxNzYxNTQwNjE1fQ.NPBTPZhPkPeMxmZKE7lgj09ARkJOIUuUpmwnk3zHQlI')
HOMEASSISTANT_URL = os.getenv('HOMEASSISTANT_URL', 'http://homeassistant:8123')
HOMEASSISTANT_TOKEN = os.getenv('HOMEASSISTANT_TOKEN')
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
            'home_assistant': 'configured' if HOMEASSISTANT_TOKEN else 'not configured',
            'tomtom': 'configured' if TOMTOM_API_KEY else 'not configured'
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


# =============================================================================
# HOME ASSISTANT HELPERS
# =============================================================================

@app.route('/api/homeassistant/locations')
def ha_locations():
    """Get family member locations from Home Assistant"""
    try:
        if not HOMEASSISTANT_TOKEN:
            return jsonify({'error': 'Home Assistant not configured'}), 503

        headers = {
            'Authorization': f'Bearer {HOMEASSISTANT_TOKEN}',
            'Content-Type': 'application/json'
        }

        response = requests.get(
            f'{HOMEASSISTANT_URL}/api/states',
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        states = response.json()

        # Filter for person entities
        persons = []
        for entity in states:
            if entity['entity_id'].startswith('person.'):
                persons.append({
                    'name': entity['attributes'].get('friendly_name'),
                    'location': entity['state'],
                    'latitude': entity['attributes'].get('latitude'),
                    'longitude': entity['attributes'].get('longitude'),
                    'last_updated': entity['last_updated']
                })

        return jsonify({'persons': persons})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Clear weather API cache on startup
    get_weather_api.cache_clear()

    # Run server
    app.run(host='0.0.0.0', port=5200, debug=False)
