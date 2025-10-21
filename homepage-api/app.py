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
from functools import lru_cache
from ftplib import FTP
from io import BytesIO
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
TRANSPORT_NSW_API_KEY = os.getenv('TRANSPORT_NSW_API_KEY')
HOMEASSISTANT_URL = os.getenv('HOMEASSISTANT_URL', 'http://homeassistant:8123')
HOMEASSISTANT_TOKEN = os.getenv('HOMEASSISTANT_TOKEN')
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY')

# BOM FTP configuration
BOM_FTP_HOST = 'ftp.bom.gov.au'
BOM_FTP_PATH = '/anon/gen/fwo/'
BOM_NSW_OBSERVATIONS_FILE = 'IDN60920.xml'  # NSW state observations
BOM_PARRAMATTA_STATION = 'Parramatta'  # Station name to search for


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
# BOM WEATHER
# =============================================================================

@app.route('/api/bom/weather')
@lru_cache(maxsize=1)
def bom_weather():
    """
    Fetch weather data from Australian BOM for Parramatta area via FTP
    Parses XML observations file to find Parramatta station data
    Cached for 5 minutes to respect BOM servers
    """
    try:
        # Connect to BOM FTP server
        ftp = FTP(BOM_FTP_HOST, timeout=10)
        ftp.login()  # Anonymous login
        ftp.cwd(BOM_FTP_PATH)

        # Download XML file
        file_data = BytesIO()
        ftp.retrbinary(f'RETR {BOM_NSW_OBSERVATIONS_FILE}', file_data.write)
        ftp.quit()

        # Parse XML
        file_data.seek(0)
        tree = ET.parse(file_data)
        root = tree.getroot()

        # Find Parramatta station by description attribute
        station_data = None
        for station in root.findall('.//station'):
            description = station.get('description', '')
            if BOM_PARRAMATTA_STATION in description:
                station_data = station
                break

        if station_data is None:
            return jsonify({'error': 'Parramatta station not found in BOM data'}), 404

        # Extract weather data from XML elements
        # BOM uses <element type="air_temperature">23.0</element> format
        def get_element_value(parent, element_type, default=None):
            element = parent.find(f".//element[@type='{element_type}']")
            return element.text if element is not None and element.text else default

        # Get station metadata from attributes
        station_name = station_data.get('description', 'Parramatta')
        time_local = station_data.find('.//period').get('time-local') if station_data.find('.//period') is not None else None

        weather_data = {
            'current': {
                'temp': float(get_element_value(station_data, 'air_temperature')) if get_element_value(station_data, 'air_temperature') else None,
                'apparent_temp': float(get_element_value(station_data, 'apparent_temp')) if get_element_value(station_data, 'apparent_temp') else None,
                'humidity': int(get_element_value(station_data, 'rel-humidity')) if get_element_value(station_data, 'rel-humidity') else None,
                'wind_speed_kmh': int(get_element_value(station_data, 'wind_spd_kmh')) if get_element_value(station_data, 'wind_spd_kmh') else None,
                'wind_dir': get_element_value(station_data, 'wind_dir', 'N/A'),
                'rain_since_9am': get_element_value(station_data, 'rainfall', '0'),
                'description': get_element_value(station_data, 'weather', 'N/A')
            },
            'station': {
                'name': station_name,
                'location': 'North Parramatta, NSW'
            },
            'updated': time_local
        }

        return jsonify(weather_data)

    except ET.ParseError as e:
        return jsonify({'error': f'Failed to parse BOM XML: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to fetch BOM data: {str(e)}'}), 500


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
            departures.append({
                'time': event.get('departureTimePlanned'),
                'destination': transportation.get('destination', {}).get('name'),
                'line': transportation.get('number'),
                'platform': transportation.get('origin', {}).get('platform'),
                'realtime': event.get('isRealtimeControlled', False),
                'delay_minutes': event.get('departureTimeEstimated', 0) - event.get('departureTimePlanned', 0) if event.get('isRealtimeControlled') else 0
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
    # Clear cache on startup
    bom_weather.cache_clear()

    # Run server
    app.run(host='0.0.0.0', port=5200, debug=False)
