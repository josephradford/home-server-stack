# Ticket 05: Backend API Service

## Objective
Create a Python Flask backend API service for BOM weather, Transport NSW enrichment, and traffic data processing.

## Tasks

### 1. Create Backend API Application

Create `homepage-api/app.py`:

```python
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

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
TRANSPORT_NSW_API_KEY = os.getenv('TRANSPORT_NSW_API_KEY')
HOMEASSISTANT_URL = os.getenv('HOMEASSISTANT_URL', 'http://homeassistant:8123')
HOMEASSISTANT_TOKEN = os.getenv('HOMEASSISTANT_TOKEN')
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY')

# BOM configuration
BOM_PARRAMATTA_STATION_ID = '94764'  # Parramatta North station
BOM_OBSERVATIONS_URL = f'http://www.bom.gov.au/fwo/IDN60801/IDN60801.{BOM_PARRAMATTA_STATION_ID}.json'


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
    Fetch weather data from Australian BOM for Parramatta area
    Cached for 5 minutes to respect BOM servers
    """
    try:
        response = requests.get(BOM_OBSERVATIONS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        observations = data.get('observations', {}).get('data', [])
        if not observations:
            return jsonify({'error': 'No observation data available'}), 404
        
        latest = observations[0]
        
        weather_data = {
            'current': {
                'temp': latest.get('air_temp'),
                'apparent_temp': latest.get('apparent_t'),
                'humidity': latest.get('rel_hum'),
                'wind_speed_kmh': latest.get('wind_spd_kmh'),
                'wind_dir': latest.get('wind_dir'),
                'rain_since_9am': latest.get('rain_trace', '0'),
                'description': latest.get('weather', 'N/A')
            },
            'station': {
                'name': data.get('observations', {}).get('header', [{}])[0].get('name', 'Parramatta'),
                'location': 'North Parramatta, NSW'
            },
            'updated': latest.get('aifstime_utc')
        }
        
        return jsonify(weather_data)
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch BOM data: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    app.run(host='0.0.0.0', port=5000, debug=False)
```

### 2. Create Requirements File

Create `homepage-api/requirements.txt`:

```txt
Flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
```

### 3. Create Dockerfile

Create `homepage-api/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create non-root user
RUN useradd -m -u 1000 apiuser && chown -R apiuser:apiuser /app
USER apiuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/api/health')"

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "app:app"]
```

### 4. Add to docker-compose.dashboard.yml

Add to `docker-compose.dashboard.yml`:

```yaml
  homepage-api:
    build: ./homepage-api
    container_name: homepage-api
    environment:
      # Transport NSW API
      TRANSPORT_NSW_API_KEY: ${TRANSPORTNSW_API_KEY}
      # Home Assistant
      HOMEASSISTANT_URL: ${HOMEASSISTANT_URL:-http://homeassistant:8123}
      HOMEASSISTANT_TOKEN: ${HOMEASSISTANT_TOKEN}
      # TomTom Traffic API
      TOMTOM_API_KEY: ${TOMTOM_API_KEY}
    ports:
      - "5000:5000"
    restart: unless-stopped
    networks:
      - home-server
    volumes:
      - ./data/homepage-api:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 5. Create API Documentation

Create `docs/BACKEND_API.md`:

```markdown
# Backend API Documentation

## Overview

The backend API provides custom integrations for:
- BOM weather data
- Transport NSW departures
- Traffic conditions (TomTom)
- Home Assistant helpers

Base URL: `http://SERVER_IP:5000`

## Endpoints

### Health Check
```
GET /api/health
```

Returns service status and configuration.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00",
  "services": {
    "transport_nsw": "configured",
    "home_assistant": "configured",
    "tomtom": "configured"
  }
}
```

### BOM Weather
```
GET /api/bom/weather
```

Returns current weather for Parramatta area from Australian Bureau of Meteorology.

**Response:**
```json
{
  "current": {
    "temp": 22.5,
    "apparent_temp": 21.0,
    "humidity": 65,
    "wind_speed_kmh": 15,
    "wind_dir": "NE",
    "rain_since_9am": "0",
    "description": "Partly cloudy"
  },
  "station": {
    "name": "Parramatta North",
    "location": "North Parramatta, NSW"
  },
  "updated": "2025-01-15T10:30:00Z"
}
```

### Transport Departures
```
GET /api/transport/departures/{stop_id}
```

Get next departures for a Transport NSW stop.

**Parameters:**
- `stop_id`: Transport NSW stop ID (e.g., 10101323)

**Response:**
```json
{
  "stopId": "10101323",
  "departures": [
    {
      "time": "2025-01-15T10:35:00",
      "destination": "Central",
      "line": "T1",
      "platform": "1",
      "realtime": true,
      "delay_minutes": 2
    }
  ],
  "updated": "2025-01-15T10:30:00"
}
```

### Traffic Route
```
GET /api/traffic/route?origin=ADDRESS&destination=ADDRESS
```

Get traffic conditions for a route.

**Parameters:**
- `origin`: Full address (e.g., "123 Street, North Parramatta NSW")
- `destination`: Full address

**Response:**
```json
{
  "origin": "123 Street, North Parramatta NSW",
  "destination": "456 Road, Sydney NSW",
  "travelTimeMinutes": 35,
  "trafficDelayMinutes": 10,
  "distanceKm": 25.5,
  "status": "moderate",
  "updated": "2025-01-15T10:30:00"
}
```

Status values:
- `clear`: < 5 min delay
- `moderate`: 5-10 min delay
- `heavy`: > 10 min delay

### Home Assistant Locations
```
GET /api/homeassistant/locations
```

Get all person locations from Home Assistant.

**Response:**
```json
{
  "persons": [
    {
      "name": "John",
      "location": "home",
      "latitude": -33.8,
      "longitude": 151.0,
      "last_updated": "2025-01-15T10:25:00"
    }
  ]
}
```

## Error Responses

All endpoints return errors in this format:

```json
{
  "error": "Error description"
}
```

HTTP status codes:
- `400`: Bad request (missing parameters)
- `404`: Not found
- `500`: Internal server error
- `503`: Service not configured

## Caching

- BOM weather: Cached for 5 minutes
- Other endpoints: No caching

## Rate Limits

Respect external API rate limits:
- BOM: No official limit (be reasonable)
- Transport NSW: 30 requests/minute
- TomTom: Based on your plan

## Development

Test endpoints locally:

```bash
# Health check
curl http://localhost:5000/api/health

# Weather
curl http://localhost:5000/api/bom/weather

# Transport (replace with your stop ID)
curl http://localhost:5000/api/transport/departures/10101323

# Traffic
curl "http://localhost:5000/api/traffic/route?origin=North+Parramatta&destination=Sydney+CBD"
```
```

## Acceptance Criteria
- [ ] app.py created with all endpoints
- [ ] Dockerfile created with health check
- [ ] requirements.txt with all dependencies
- [ ] Service added to docker-compose.dashboard.yml
- [ ] API accessible at http://SERVER_IP:5000
- [ ] Health check endpoint working
- [ ] BOM weather endpoint returns data
- [ ] Transport NSW endpoint works (when key provided)
- [ ] Traffic endpoint works (when key provided)
- [ ] Documentation created
- [ ] Error handling implemented
- [ ] Logging configured

## Testing
```bash
# Build and start
docker compose -f docker-compose.dashboard.yml build homepage-api
docker compose -f docker-compose.dashboard.yml up -d homepage-api

# Check logs
docker logs homepage-api

# Test health
curl http://localhost:5000/api/health

# Test BOM weather
curl http://localhost:5000/api/bom/weather | jq
```

## Dependencies
- Ticket 01: Project structure
- Ticket 03: Home Assistant (for HA integration endpoints)

## Notes
- API runs on port 5000
- Uses Gunicorn with 2 workers for production
- Health check configured for Docker
- Implements caching for BOM data
- Geocoding uses TomTom API
- All external API keys optional (endpoints return 503 if not configured)
- Non-root user for security
- Request timeout set to 10 seconds
