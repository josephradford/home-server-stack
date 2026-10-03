"""
Homepage Dashboard Backend API
Provides custom endpoints for:
- BOM weather data (Australian Bureau of Meteorology)
- Transport NSW data enrichment
- Traffic conditions (TomTom API)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import parse_qs
import os
import re
import json
from functools import lru_cache, wraps
import xml.etree.ElementTree as ET
from weather_au import api as weather_api
from traffic_scheduler import get_active_routes, is_route_active

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
TRANSPORT_NSW_API_KEY = os.getenv('TRANSPORT_NSW_API_KEY')
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY')
ADGUARD_USERNAME = os.getenv('ADGUARD_USERNAME')
ADGUARD_PASSWORD = os.getenv('ADGUARD_PASSWORD')
ADGUARD_URL = os.getenv('ADGUARD_URL', 'http://adguard:80')
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
SYDNEY_TZ = ZoneInfo('Australia/Sydney')
COMMUTE_CUTOVER_HOUR = int(os.getenv('TRANSPORT_COMMUTE_CUTOVER_HOUR', '12'))

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
    Get Transport NSW departures with enhanced data.
    Optional query params:
      destination - filter by destination substring (case-insensitive)
      routes - comma-separated route numbers to include
      limit - max results (default 5)
    """
    try:
        if not TRANSPORT_NSW_API_KEY:
            return jsonify({'error': 'Transport NSW API key not configured'}), 503

        dest_filter = request.args.get('destination', '').lower()
        routes_filter = [r.strip() for r in request.args.get('routes', '').split(',') if r.strip()]
        limit = int(request.args.get('limit', 15))

        departures = _fetch_departures(stop_id, dest_filter, routes_filter, limit)

        return jsonify({
            'stopId': stop_id,
            'departures': departures,
            'updated': datetime.now().isoformat()
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Transport API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _fetch_departures(stop_id, dest_filter, routes_filter, limit):
    """Return filtered departures for a stop. Raises on upstream failure."""
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

    departures = []
    stop_events = data.get('stopEvents', [])
    for event in stop_events:
        if len(departures) >= limit:
            break

        if event.get('isCancelled'):
            continue

        transportation = event.get('transportation', {})
        destination_name = transportation.get('destination', {}).get('name', '')
        route_number = transportation.get('number', '')

        if dest_filter and dest_filter not in destination_name.lower():
            continue
        if routes_filter and route_number not in routes_filter:
            continue

        location = event.get('location', {})
        is_realtime = event.get('isRealtimeControlled', False)

        delay_minutes = 0
        departure_time = event.get('departureTimePlanned')
        if is_realtime:
            estimated_str = event.get('departureTimeEstimated')
            if estimated_str:
                departure_time = estimated_str
            try:
                planned_str = event.get('departureTimePlanned')
                if planned_str and estimated_str:
                    planned = datetime.fromisoformat(planned_str.replace('Z', '+00:00'))
                    estimated = datetime.fromisoformat(estimated_str.replace('Z', '+00:00'))
                    delay_minutes = int((estimated - planned).total_seconds() / 60)
            except (ValueError, AttributeError):
                delay_minutes = 0

        departures.append({
            'time': departure_time,
            'destination': destination_name,
            'line': route_number,
            'platform': location.get('properties', {}).get('platformName'),
            'realtime': is_realtime,
            'delay_minutes': delay_minutes
        })
    return departures


def _sydney_now():
    return datetime.now(SYDNEY_TZ)


def _commute_stop(number):
    """Stop ID, display name and filters for TRANSPORT_STOP_<number> from env."""
    query = parse_qs(os.getenv(f'TRANSPORT_STOP_{number}_FILTER', ''))
    dest = query.get('destination', [''])[0].lower()
    routes = [r.strip() for r in query.get('routes', [''])[0].split(',') if r.strip()]
    return (
        os.getenv(f'TRANSPORT_STOP_{number}_ID', ''),
        os.getenv(f'TRANSPORT_STOP_{number}_NAME', f'Stop {number}'),
        dest,
        routes,
    )


@app.route('/api/transport/commute')
def transport_commute():
    """
    Next departures for the commute direction that applies right now.
    Before the cutover hour (Sydney time) it shows the 'to' stops (1 and 2);
    from the cutover onward it shows the 'from' stops (3 and 4).
    """
    now = _sydney_now()
    to_work = now.hour < COMMUTE_CUTOVER_HOUR
    stop_numbers = (1, 2) if to_work else (3, 4)
    direction = (os.getenv('TRANSPORT_SECTION_1', 'To Parramatta') if to_work
                 else os.getenv('TRANSPORT_SECTION_2', 'From Parramatta'))
    try:
        if not TRANSPORT_NSW_API_KEY:
            return jsonify({'error': 'Transport NSW API key not configured'}), 503

        departures = []
        for number in stop_numbers:
            stop_id, stop_name, dest, routes = _commute_stop(number)
            for departure in _fetch_departures(stop_id, dest, routes, limit=4):
                departure['stop'] = stop_name
                departures.append(departure)

        departures.sort(key=lambda d: d['time'] or '')
        return jsonify({
            'direction': direction,
            'departures': departures[:4],
            'updated': now.isoformat()
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
# EXTERNAL SERVICE OUTAGE STATUS
# =============================================================================
# Bellwethers: large infra providers whose outages tend to take unrelated
# sites down with them. Personal: services this household specifically
# depends on. Each poller is best-effort — a provider that's unreachable or
# whose response shape has changed reports 'unknown' rather than failing the
# whole endpoint. Results are cached for 5 minutes to avoid hammering these
# (mostly free, rate-limit-sensitive) public endpoints.

_STATUS_HEADERS = {'User-Agent': 'Mozilla/5.0 (homepage-api outage-status poller)'}


@timed_lru_cache(seconds=300)
def _poll_statuspage(name, url):
    """Generic poller for providers on Atlassian Statuspage (GitHub, Docker
    Hub, Cloudflare, etc.) — they all share the same /api/v2/status.json shape."""
    try:
        response = requests.get(url, headers=_STATUS_HEADERS, timeout=10)
        response.raise_for_status()
        status_data = response.json()['status']
        status = 'operational' if status_data.get('indicator') == 'none' else 'issue'
        return {'name': name, 'status': status, 'detail': status_data.get('description', '')}
    except Exception as e:
        return {'name': name, 'status': 'unknown', 'detail': str(e)}


@timed_lru_cache(seconds=300)
def _poll_rss_feed(name, url):
    """Generic poller for RSS-based status feeds (AWS, Azure). These feeds
    only contain items for events — an empty feed means no current/recent
    event. When an item is present, treat it as resolved only if its text
    says so, otherwise treat it as an ongoing issue."""
    try:
        response = requests.get(url, headers=_STATUS_HEADERS, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = root.findall('.//item')
        if not items:
            return {'name': name, 'status': 'operational', 'detail': 'No recent events'}
        title = items[0].findtext('title') or ''
        description = items[0].findtext('description') or ''
        text = f'{title} {description}'.lower()
        if 'resolved' in text or 'operating normally' in text:
            return {'name': name, 'status': 'operational', 'detail': title}
        return {'name': name, 'status': 'issue', 'detail': title}
    except Exception as e:
        return {'name': name, 'status': 'unknown', 'detail': str(e)}


@timed_lru_cache(seconds=300)
def _poll_gcp():
    try:
        response = requests.get('https://status.cloud.google.com/incidents.json',
                                 headers=_STATUS_HEADERS, timeout=10)
        response.raise_for_status()
        active = [i for i in response.json() if not i.get('end')]
        if not active:
            return {'name': 'Google Cloud', 'status': 'operational', 'detail': 'All services normal'}
        return {'name': 'Google Cloud', 'status': 'issue',
                'detail': active[0].get('external_desc', 'Active incident')}
    except Exception as e:
        return {'name': 'Google Cloud', 'status': 'unknown', 'detail': str(e)}


def _poll_aws():
    """Aggregates a few Sydney-region feeds plus one global service, since
    AWS has no single aggregate status endpoint."""
    feeds = [
        ('EC2 (Sydney)', 'https://status.aws.amazon.com/rss/ec2-ap-southeast-2.rss'),
        ('S3 (Sydney)', 'https://status.aws.amazon.com/rss/s3-ap-southeast-2.rss'),
        ('CloudFront (Global)', 'https://status.aws.amazon.com/rss/cloudfront.rss'),
    ]
    results = [_poll_rss_feed(name, url) for name, url in feeds]
    if any(r['status'] == 'issue' for r in results):
        overall = 'issue'
    elif any(r['status'] == 'unknown' for r in results):
        overall = 'unknown'
    else:
        overall = 'operational'
    problems = [f"{r['name']}: {r['detail']}" for r in results if r['status'] != 'operational']
    detail = '; '.join(problems) if problems else 'All checked services normal'
    return {'name': 'AWS (ap-southeast-2)', 'status': overall, 'detail': detail}


@timed_lru_cache(seconds=300)
def _poll_icloud():
    try:
        response = requests.get(
            'https://www.apple.com/support/systemstatus/data/system_status_en_US.js',
            headers=_STATUS_HEADERS, timeout=10
        )
        response.raise_for_status()
        services = response.json().get('services', [])
        icloud_services = [s for s in services if s.get('serviceName', '').startswith('iCloud')]

        active_issues = []
        for service in icloud_services:
            for event in service.get('events', []):
                if event.get('eventStatus') != 'resolved':
                    active_issues.append(f"{service['serviceName']}: {event.get('message', 'issue')}")

        if not active_issues:
            return {'name': 'iCloud', 'status': 'operational', 'detail': 'All iCloud services normal'}
        return {'name': 'iCloud', 'status': 'issue', 'detail': '; '.join(active_issues)}
    except Exception as e:
        return {'name': 'iCloud', 'status': 'unknown', 'detail': str(e)}


_ATOM_NS = {'a': 'http://www.w3.org/2005/Atom'}


@timed_lru_cache(seconds=300)
def _poll_google_workspace():
    try:
        response = requests.get('https://www.google.com/appsstatus/dashboard/feed.atom',
                                 headers=_STATUS_HEADERS, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        entries = root.findall('a:entry', _ATOM_NS)
        gmail_entries = [
            e for e in entries
            if 'gmail' in (e.findtext('a:title', default='', namespaces=_ATOM_NS) or '').lower()
        ]
        if not gmail_entries:
            return {'name': 'Google Workspace (Gmail)', 'status': 'operational',
                     'detail': 'No recent incidents mentioning Gmail'}

        latest_title = gmail_entries[0].findtext('a:title', default='', namespaces=_ATOM_NS) or ''
        status = 'operational' if latest_title.strip().upper().startswith('RESOLVED') else 'issue'
        detail = latest_title.splitlines()[0][:200] if latest_title else 'Recent Gmail incident'
        return {'name': 'Google Workspace (Gmail)', 'status': status, 'detail': detail}
    except Exception as e:
        return {'name': 'Google Workspace (Gmail)', 'status': 'unknown', 'detail': str(e)}


def _outage_snapshot():
    return {
        'bellwethers': [
            _poll_statuspage('Cloudflare', 'https://www.cloudflarestatus.com/api/v2/status.json'),
            _poll_aws(),
            _poll_gcp(),
            _poll_rss_feed('Azure', 'https://rssfeed.azure.status.microsoft/en-us/status/feed/'),
        ],
        'personal': [
            _poll_google_workspace(),
            _poll_icloud(),
            _poll_statuspage('GitHub', 'https://www.githubstatus.com/api/v2/status.json'),
            _poll_statuspage('Docker Hub', 'https://www.dockerstatus.com/api/v2/status.json'),
        ],
    }


@app.route('/api/status/outages')
def status_outages():
    """
    Outage status for external services, split into two tiers:
    - bellwethers: major infra providers (if these are down, lots of
      unrelated sites are likely down too)
    - personal: services this household specifically depends on
    """
    try:
        snapshot = _outage_snapshot()
        bellwethers, personal = snapshot['bellwethers'], snapshot['personal']
        return jsonify({
            'bellwethers': bellwethers,
            'bellwethers_issues': sum(1 for b in bellwethers if b['status'] == 'issue'),
            'personal': personal,
            'personal_issues': sum(1 for p in personal if p['status'] == 'issue'),
            'updated': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status/health/<tier>/<int:index>')
def status_health(tier, index):
    """
    Returns 200 when the provider reports operational, 503 otherwise.
    Lets Homepage's siteMonitor show a green/red dot per provider.
    """
    if tier not in ('bellwethers', 'personal'):
        return jsonify({'error': 'unknown tier'}), 404
    try:
        providers = _outage_snapshot()[tier]
        provider = providers[index]
    except IndexError:
        return jsonify({'error': 'unknown provider'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 503
    if provider['status'] == 'operational':
        return jsonify(provider), 200
    return jsonify(provider), 503


# =============================================================================
# NETWORK: DEVICES + ISP/LOCAL HEALTH
# =============================================================================

@app.route('/api/network/devices')
def network_devices():
    """
    List devices AdGuard has seen on the network recently (DHCP + DNS clients).
    Not a live ARP scan — reflects whatever AdGuard has already observed.
    """
    try:
        if not (ADGUARD_USERNAME and ADGUARD_PASSWORD):
            return jsonify({'error': 'AdGuard credentials not configured'}), 503

        response = requests.get(
            f'{ADGUARD_URL}/control/clients',
            auth=(ADGUARD_USERNAME, ADGUARD_PASSWORD),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        devices = []
        for client in data.get('auto_clients', []):
            devices.append({
                'name': client.get('name') or client.get('ip'),
                'ip': client.get('ip'),
                'source': client.get('source')
            })

        return jsonify({
            'devices': devices,
            'count': len(devices),
            'updated': datetime.now().isoformat()
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'AdGuard API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _prometheus_query(query):
    """Run an instant PromQL query, return the `result` list of the response."""
    response = requests.get(
        f'{PROMETHEUS_URL}/api/v1/query',
        params={'query': query},
        timeout=10
    )
    response.raise_for_status()
    data = response.json()
    if data.get('status') != 'success':
        raise RuntimeError(data.get('error', 'Prometheus query failed'))
    return data['data']['result']


# Must match the targets configured in monitoring/prometheus/prometheus.yml's
# 'blackbox-icmp' job, keyed by role so the homepage widget can reference
# stable field names instead of array positions.
_NETWORK_PROBE_TARGETS = {
    'router': os.getenv('ROUTER_IP', '192.168.1.1'),
    'isp': '1.1.1.1',
    'isp_secondary': '8.8.8.8',
}


@app.route('/api/network/health')
def network_health():
    """
    Local network / ISP health, derived from blackbox_exporter ICMP probes.
    Reports current latency + packet loss (24h window) per probed target.
    """
    try:
        latency_results = _prometheus_query('probe_duration_seconds{job="blackbox-icmp"}')
        loss_results = _prometheus_query(
            '(1 - avg_over_time(probe_success{job="blackbox-icmp"}[24h])) * 100'
        )

        latency_by_instance = {
            r['metric'].get('instance'): float(r['value'][1]) * 1000  # seconds -> ms
            for r in latency_results
        }
        loss_by_instance = {
            r['metric'].get('instance'): float(r['value'][1])
            for r in loss_results
        }

        probes = {}
        for role, instance in _NETWORK_PROBE_TARGETS.items():
            probes[role] = {
                'target': instance,
                'latency_ms': round(latency_by_instance[instance], 1) if instance in latency_by_instance else None,
                'packet_loss_pct_24h': round(loss_by_instance[instance], 2) if instance in loss_by_instance else None
            }

        return jsonify({
            'probes': probes,
            'updated': datetime.now().isoformat()
        })

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Prometheus API error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# WIREGUARD VPN STATUS
# =============================================================================

def _wg_interface_up():
    """Return True if the wg0 network interface exists in the host sysfs.
    Uses os.listdir rather than os.path.isdir because sysfs symlinks don't
    resolve correctly inside a container with a bind-mounted /sys/class/net.
    """
    try:
        return 'wg0' in os.listdir('/sys/class/net')
    except Exception:
        return False


@app.route('/api/wireguard/status')
def wireguard_status():
    """
    Get WireGuard VPN status by inspecting the host sysfs.
    No systemctl or wg CLI required — works inside a container.
    """
    try:
        up = _wg_interface_up()
        if not up:
            return jsonify({
                'status': 'Inactive',
                'interface': 'wg0 (down)',
                'service_status': 'inactive',
                'updated': datetime.now().isoformat()
            })

        return jsonify({
            'status': 'Active',
            'interface': 'wg0 (up)',
            'service_status': 'active',
            'updated': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


# =============================================================================
# DOCKER DAEMON STATUS
# =============================================================================

def _docker_api(path):
    """
    Make a GET request to the Docker daemon via its Unix socket.
    No docker CLI or SDK required.
    """
    import http.client
    import socket as _socket

    class _UnixConn(http.client.HTTPConnection):
        def connect(self):
            self.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.sock.connect('/var/run/docker.sock')

    conn = _UnixConn('localhost')
    try:
        conn.request('GET', path)
        resp = conn.getresponse()
        return json.loads(resp.read())
    finally:
        conn.close()


def _fmt_bytes(n):
    """Format a byte count as a human-readable string."""
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} PB'


@app.route('/api/docker/status')
def docker_status():
    """
    Get Docker daemon status via the Unix socket.
    No systemctl or docker CLI required — works inside a container.
    """
    try:
        info = _docker_api('/info')
        version_info = _docker_api('/version')

        running = info.get('ContainersRunning', 0)
        total = info.get('Containers', 0)
        docker_version = version_info.get('Version', 'Unknown')

        # Disk usage: sum image sizes from /system/df
        disk_usage = 'Unknown'
        try:
            df = _docker_api('/system/df')
            total_bytes = sum(img.get('Size', 0) for img in df.get('Images', []))
            disk_usage = _fmt_bytes(total_bytes)
        except Exception:
            pass

        status_text = f'Active ({running}/{total} running)'
        return jsonify({
            'status': status_text,
            'containers': f'{running}/{total}',
            'version': f'v{docker_version}',
            'disk_usage': disk_usage,
            'service_status': 'active',
            'updated': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'status': 'Inactive',
            'containers': 'N/A',
            'version': 'N/A',
            'disk_usage': 'N/A',
            'service_status': 'unknown',
            'error': str(e),
            'updated': datetime.now().isoformat()
        })


def _docker_logs(name, tail=250):
    """
    Return recent combined stdout/stderr logs for a container as text.
    The Docker logs endpoint returns a multiplexed stream: each frame is an
    8-byte header (stream byte, 3 zero bytes, 4-byte big-endian length)
    followed by the payload. Strip the headers.
    """
    import http.client
    import socket as _socket

    class _UnixConn(http.client.HTTPConnection):
        def connect(self):
            self.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.sock.connect('/var/run/docker.sock')

    conn = _UnixConn('localhost')
    try:
        conn.request('GET', f'/containers/{name}/logs?stdout=1&stderr=1&timestamps=1&tail={tail}')
        resp = conn.getresponse()
        if resp.status >= 400:
            return ''
        raw = resp.read()
    finally:
        conn.close()

    return _demux_docker_stream(raw)


def _demux_docker_stream(raw):
    """Strip the 8-byte frame headers from a multiplexed Docker log stream."""
    import struct

    out = []
    i = 0
    while i + 8 <= len(raw):
        header = raw[i:i + 8]
        # If this doesn't look like a frame header (no-TTY containers always
        # send headers; guard anyway), treat the rest as plain text.
        if header[0] in (0, 1, 2) and header[1:4] == b'\x00\x00\x00':
            (length,) = struct.unpack('>I', header[4:8])
            out.append(raw[i + 8:i + 8 + length].decode('utf-8', 'replace'))
            i += 8 + length
        else:
            out.append(raw[i:].decode('utf-8', 'replace'))
            break
    return ''.join(out)


_ICLOUDPD_CONTAINER = 'icloudpd'

# Log substrings, checked case-insensitively. Tune against real output on the
# server; keep the lists here so tuning is a one-line change.
_ICLOUDPD_AUTH_MARKERS = (
    'invalid authentication token',
    'waiting for mfa',
    'two-step authentication',
    'two-factor authentication',
    'password is required',
    'failed to login',
)
_ICLOUDPD_DRIVE_MARKER = 'backup drive not mounted or wrong drive'
_ICLOUDPD_DONE_MARKERS = (
    'all photos have been downloaded',
    'iteration completed',
)
_ICLOUDPD_PROGRESS_MARKERS = (
    'downloading ',
    'downloaded ',
)
_ICLOUDPD_USER_MARKER = 'processing user:'

# Worst status wins when combining multiple accounts' results.
_ICLOUDPD_SEVERITY = {'auth_required': 3, 'syncing': 2, 'unknown': 1, 'ok': 0}


def _rel_time(iso_ts):
    """'2026-09-06T04:15:03Z' -> '3 hours ago' (coarse)."""
    try:
        s = iso_ts.replace('Z', '+00:00')
        # Docker emits nanosecond precision; datetime accepts at most microseconds
        s = re.sub(r'(\.\d{6})\d+', r'\1', s)
        ts = datetime.fromisoformat(s)
    except (ValueError, AttributeError, TypeError):
        return None
    delta = datetime.now(ts.tzinfo) - ts
    secs = int(delta.total_seconds())
    if secs < 0:
        return 'just now'
    for unit, size in (('day', 86400), ('hour', 3600), ('minute', 60)):
        if secs >= size:
            n = secs // size
            return f'{n} {unit}{"s" if n != 1 else ""} ago'
    return 'just now'


def _classify_account_segment(seg_lines, seg_lower, empty_status='unknown',
                               empty_label='Unknown', empty_message='No recent activity in logs'):
    """Classify one account's slice of the log, newest line wins (same logic
    as the original single-account classifier). `empty_*` control the result
    when nothing in the segment matches any marker."""
    last_done_ts = None
    for ln, lo in zip(reversed(seg_lines), reversed(seg_lower)):
        if any(m in lo for m in _ICLOUDPD_AUTH_MARKERS):
            return {'status': 'auth_required', 'statusLabel': 'Re-auth needed',
                    'lastSync': last_done_ts,
                    'lastSyncRelative': _rel_time(last_done_ts) if last_done_ts else None,
                    'message': 'Apple sign-in expired — open the web UI to re-authenticate'}
        if any(m in lo for m in _ICLOUDPD_DONE_MARKERS):
            last_done_ts = ln.split(' ', 1)[0]
            return {'status': 'ok', 'statusLabel': 'OK', 'lastSync': last_done_ts,
                    'lastSyncRelative': _rel_time(last_done_ts),
                    'message': 'Last sync completed'}
        if any(m in lo for m in _ICLOUDPD_PROGRESS_MARKERS):
            return {'status': 'syncing', 'statusLabel': 'Syncing', 'lastSync': None,
                    'lastSyncRelative': None, 'message': 'Sync in progress'}
    return {'status': empty_status, 'statusLabel': empty_label, 'lastSync': None,
            'lastSyncRelative': None, 'message': empty_message}


def _classify_icloudpd(state, health, logs):
    lines = [ln for ln in logs.splitlines() if ln.strip()]
    lower = [ln.lower() for ln in lines]

    running = bool(state.get('Running'))
    if not running:
        return {'status': 'down', 'statusLabel': 'Stopped', 'lastSync': None,
                'lastSyncRelative': None, 'message': 'Container is not running'}

    _drive_result = {'status': 'drive_missing', 'statusLabel': 'Drive not mounted',
                     'lastSync': None, 'lastSyncRelative': None,
                     'message': 'Backup drive is not mounted or is the wrong drive'}
    if health == 'unhealthy':
        return _drive_result

    # The drive guard runs before icloudpd starts, so its failure line always
    # precedes any "Processing user:" activity from a lifetime where the guard
    # passed. Scan newest-first but stop at the first "Processing user:" line —
    # a drive-marker line older than that is from a since-recovered earlier
    # lifetime and must not pin the status.
    for lo in reversed(lower):
        if _ICLOUDPD_USER_MARKER in lo:
            break
        if _ICLOUDPD_DRIVE_MARKER in lo:
            return _drive_result

    # Split into per-account segments: each starts at a "Processing user: X"
    # line and runs to just before the next such line (or end of tail).
    segments_by_user = {}
    current_user = None
    current_lines = []
    current_lower = []
    for ln, lo in zip(lines, lower):
        idx = lo.find(_ICLOUDPD_USER_MARKER)
        if idx != -1:
            if current_user is not None:
                segments_by_user[current_user] = (current_lines, current_lower)
            current_user = ln[idx + len(_ICLOUDPD_USER_MARKER):].strip()
            current_lines = []
            current_lower = []
        else:
            current_lines.append(ln)
            current_lower.append(lo)
    if current_user is not None:
        segments_by_user[current_user] = (current_lines, current_lower)

    if not segments_by_user:
        if current_lines:
            return _classify_account_segment(current_lines, current_lower)
        return {'status': 'unknown', 'statusLabel': 'Unknown', 'lastSync': None,
                'lastSyncRelative': None, 'message': 'No recent activity in logs'}

    results = [_classify_account_segment(seg_lines, seg_lower, empty_status='syncing',
                                          empty_label='Syncing', empty_message='Sync in progress')
               for seg_lines, seg_lower in segments_by_user.values()]
    return max(results, key=lambda r: (_ICLOUDPD_SEVERITY.get(r['status'], -1), r['lastSync'] or ''))


@app.route('/api/icloudpd/status')
def icloudpd_status():
    name = _ICLOUDPD_CONTAINER
    try:
        info = _docker_api(f'/containers/{name}/json')
        state = info.get('State', {}) or {}
        health = (state.get('Health') or {}).get('Status')
        logs = _docker_logs(name, tail=500)
        result = _classify_icloudpd(state, health, logs)
    except Exception as e:
        result = {'status': 'unknown', 'statusLabel': 'Unknown', 'lastSync': None,
                  'lastSyncRelative': None, 'message': f'Cannot read container state: {e}'}
    result['name'] = name
    return jsonify(result)


if __name__ == '__main__':
    # Clear weather API cache on startup
    get_weather_api.cache_clear()

    # Run server
    app.run(host='0.0.0.0', port=5200, debug=False)
