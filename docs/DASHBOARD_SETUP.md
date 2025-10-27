# Dashboard Setup Guide

Complete guide for setting up the Homepage dashboard with transport, traffic, calendar, and monitoring integrations.

## Quick Start

1. Copy and configure environment:
   ```bash
   cp .env.example .env
   nano .env  # Fill in your values
   ```

2. Get API keys:
   - **Transport NSW**: https://opendata.transport.nsw.gov.au/ (free, 10k requests/month)
   - **TomTom Traffic**: https://developer.tomtom.com/ (free, 2.5k requests/day)
   - **Google Calendar**: Settings → Integrate calendar → Copy "Secret iCal URL"

3. Deploy services:
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d
   ```

4. Access dashboard:
   - Homepage: http://SERVER_IP:3100

## Widget Configuration

### Why Duplicate Environment Variables?

Both `homepage` and `homepage-api` services need similar variables for different reasons:

- **homepage** needs them for **template substitution** in `services.yaml`
  - Example: `{{HOMEPAGE_VAR_TRANSPORT_STOP_1_ID}}` → `10101323` when service starts
  - Widget URLs and labels are built from these templates

- **homepage-api** needs them for **backend logic**
  - Makes actual API calls to Transport NSW, TomTom
  - Determines which routes are active based on schedules
  - Returns real-time data to widgets

### Transport Widgets

**Find Stop IDs**:
1. Visit https://transportnsw.info/
2. Search for your station/stop
3. URL shows the stop ID: `transportnsw.info/stop?q=10101323`

**Configure in .env**:
```bash
TRANSPORT_STOP_1_ID=10101323
TRANSPORT_STOP_1_NAME="North Parra Platform 1"
TRANSPORT_STOP_1_ICON=mdi-train

TRANSPORT_STOP_2_ID=2093456
TRANSPORT_STOP_2_NAME="Bus Stop - Church St"
TRANSPORT_STOP_2_ICON=mdi-bus
```

**Available Icons**: `mdi-train`, `mdi-bus`, `mdi-ferry`, `mdi-tram`, `mdi-subway`
Browse more: https://pictogrammers.com/library/mdi/

### Traffic Widgets

**Schedule Format**: `DAYS START-END` (24-hour time)
- `Mon-Fri 07:00-09:00` - Weekday mornings only
- `Mon-Fri 17:00-19:00` - Weekday evenings only
- `Sat-Sun 10:00-18:00` - Weekend daytime
- `Daily 00:00-23:59` - Always active

**Configure in .env**:
```bash
TRAFFIC_ROUTE_1_NAME="Morning Commute"
TRAFFIC_ROUTE_1_ORIGIN="123 Your Street, Parramatta NSW 2151"
TRAFFIC_ROUTE_1_DESTINATION="456 Work Street, Sydney NSW 2000"
TRAFFIC_ROUTE_1_SCHEDULE="Mon-Fri 07:00-09:00"

TRAFFIC_ROUTE_2_NAME="Evening Commute"
TRAFFIC_ROUTE_2_ORIGIN="456 Work Street, Sydney NSW 2000"
TRAFFIC_ROUTE_2_DESTINATION="123 Your Street, Parramatta NSW 2151"
TRAFFIC_ROUTE_2_SCHEDULE="Mon-Fri 17:00-19:00"
```

**Address Tips**:
- ✅ Use full addresses: "123 Church St, North Parramatta NSW 2151"
- ✅ Landmarks work: "Sydney Opera House, Sydney NSW"
- ⚠️ Suburbs less accurate: "North Parramatta"
- ❌ Generic names fail: "Home", "Work"

**Benefits of Scheduling**:
- Routes only appear during configured times
- Saves ~75% of API calls (only queries when relevant)
- Morning commute: 7-9am weekdays
- Evening commute: 5-7pm weekdays

### Calendar Widget

**Get iCal URL**:
1. Open Google Calendar → Settings (gear icon)
2. Select your calendar
3. Scroll to "Integrate calendar"
4. Copy "Secret address in iCal format"

**Configure in .env**:
```bash
GOOGLE_CALENDAR_ICAL_URL=https://calendar.google.com/calendar/ical/.../basic.ics
```

**Privacy Note**: Anyone with the iCal URL can view your calendar. To reset, click "Reset" in calendar settings.

## Widget Refresh Intervals

Configured in `config/homepage/services-template.yaml`:
- **Transport**: 60 seconds (departures change frequently)
- **Traffic**: 5 minutes (gradual updates, saves API quota)
- **Calendar**: 1 hour (events rarely change)

## Testing

Test endpoints before configuring widgets:

```bash
# Health check
curl http://localhost:5000/api/health

# Transport departures (replace STOP_ID)
curl http://localhost:5000/api/transport/departures/10101323

# Traffic route
curl "http://localhost:5000/api/traffic/route?origin=Parramatta&destination=Sydney"

# Active routes (check scheduling)
curl http://localhost:5000/api/traffic/active-routes
```

## Troubleshooting

### Transport not showing
- Verify stop ID at transportnsw.info
- Check API key: `TRANSPORT_NSW_API_KEY` in .env
- Test: `curl http://localhost:5000/api/transport/departures/YOUR_STOP_ID`
- Check logs: `docker logs homepage-api`

### Traffic not showing
- Verify TomTom API key in .env
- Check address format (use full addresses)
- Verify route is in schedule: `curl http://localhost:5000/api/traffic/active-routes`
- Check logs: `docker logs homepage-api`

### Calendar not showing
- Verify iCal URL starts with `https://calendar.google.com`
- Test URL in browser (should download .ics file)
- Check logs: `docker logs homepage`

### Wrong schedule times
- Use 24-hour format: `07:00` not `7:00 AM`
- Check server time: `docker exec homepage-api date`
- Restart after .env changes: `docker compose -f docker-compose.dashboard.yml restart`

### 503 Service Unavailable
- Missing API key in .env
- Restart services after updating .env
- Check health: `curl http://localhost:5000/api/health`

## API Quota Management

**Transport NSW** (10,000 requests/month):
- 1 widget × 60 requests/hour = 1,440/day = ~43,200/month
- Limit to 1-2 transport widgets

**TomTom** (2,500 requests/day):
- 1 widget × 12 requests/hour = 288/day
- Can run 5-8 traffic widgets comfortably
- Use scheduling to reduce calls (~75% savings)

## Security Best Practices

- Never commit .env file to git
- Keep API keys private
- Rotate keys if exposed
- iCal URLs are semi-public (anyone with URL can view)
- Monitor API usage in provider dashboards

## Example Response Formats

**Transport Departures**:
```json
{
  "stopId": "10101323",
  "departures": [{
    "destination": "Hornsby via Gordon",
    "line": "T1 North Shore & Western Line",
    "platform": "Platform 1",
    "time": "2025-10-27T08:17:00Z",
    "realtime": true,
    "delay_minutes": 0
  }]
}
```

**Traffic Route**:
```json
{
  "travelTimeMinutes": 35,
  "trafficDelayMinutes": 5,
  "distanceKm": 24.5,
  "status": "moderate"
}
```

**Active Routes**:
```json
{
  "routes": [{
    "name": "Morning Commute",
    "origin": "123 Home St, Parramatta NSW",
    "destination": "456 Work St, Sydney NSW",
    "route_num": 1,
    "schedule": "Mon-Fri 07:00-09:00"
  }],
  "count": 1
}
```
