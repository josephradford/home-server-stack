# Backend API Documentation

## Overview

The backend API provides custom integrations for:
- BOM weather data
- Transport NSW departures
- Traffic conditions (TomTom)
- Home Assistant helpers

**Base URL**: `https://homepage-api.${DOMAIN}` (via Traefik with SSL)
**Internal URL**: `http://homepage-api:5000` (within Docker network)

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

## Security

- Access via HTTPS with SSL certificates
- IP whitelisting via Traefik middleware (admin-secure)
- Rate limiting via Traefik (10 requests/min)
- No direct port exposure

## Development

Test endpoints locally:

```bash
# Health check
curl https://homepage-api.${DOMAIN}/api/health

# Or via internal network
docker exec homepage curl http://homepage-api:5000/api/health

# Weather
curl https://homepage-api.${DOMAIN}/api/bom/weather | jq

# Transport (replace with your stop ID)
curl https://homepage-api.${DOMAIN}/api/transport/departures/10101323 | jq

# Traffic
curl "https://homepage-api.${DOMAIN}/api/traffic/route?origin=North+Parramatta&destination=Sydney+CBD" | jq
```

## Deployment

```bash
# Build and start
make dashboard-start

# Or use docker compose
docker compose -f docker-compose.dashboard.yml build homepage-api
docker compose -f docker-compose.dashboard.yml up -d homepage-api

# Check logs
docker logs homepage-api

# Check health
docker exec homepage-api curl http://localhost:5000/api/health
```

## Configuration

Required environment variables in `.env`:

```bash
# Optional: Transport NSW API key
TRANSPORTNSW_API_KEY=your_api_key

# Optional: TomTom API key for traffic
TOMTOM_API_KEY=your_tomtom_key

# Optional: Home Assistant integration
HOMEASSISTANT_URL=http://homeassistant:8123
HOMEASSISTANT_TOKEN=your_ha_token
```

All API keys are optional. Endpoints will return 503 (Service Not Configured) if the required key is missing.
