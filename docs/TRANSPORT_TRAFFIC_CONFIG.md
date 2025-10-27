# Transport & Traffic Configuration

Complete guide for configuring Transport NSW departures, traffic routes, and Google Calendar integration for the Homepage dashboard.

## Transport Stop Configuration

###Finding Stop IDs

1. Go to https://transportnsw.info/
2. Search for your station or stop
3. Click on it
4. Copy the stop ID from the URL

**Example URL**: `https://transportnsw.info/stop?q=10101323`
**Stop ID**: `10101323`

### Configure in .env

```bash
# Stop 1 - Train Platform
TRANSPORT_STOP_1_ID=10101323
TRANSPORT_STOP_1_NAME="North Parra Platform 1"
TRANSPORT_STOP_1_ICON=mdi-train

# Stop 2 - Bus Stop
TRANSPORT_STOP_2_ID=2093456
TRANSPORT_STOP_2_NAME="Bus Stop - Church St"
TRANSPORT_STOP_2_ICON=mdi-bus

# Add more stops (STOP_3, STOP_4, etc.)
```

### Available Icons

Material Design Icons for transport:
- `mdi-train` - Train
- `mdi-bus` - Bus
- `mdi-ferry` - Ferry
- `mdi-tram` - Light rail
- `mdi-subway` - Metro

Browse all icons: https://pictogrammers.com/library/mdi/

## Traffic Route Configuration

### Schedule Format

Format: `DAYS START_TIME-END_TIME`

**Examples**:
- `Mon-Fri 07:00-09:00` - Weekday mornings
- `Mon-Fri 17:00-19:00` - Weekday evenings
- `Daily 00:00-23:59` - All day, every day
- `Sat-Sun 10:00-18:00` - Weekends only
- `Mon 08:00-09:00` - Monday mornings only

### Configure in .env

```bash
# Route 1: Morning Commute
TRAFFIC_ROUTE_1_NAME="Morning Commute"
TRAFFIC_ROUTE_1_ORIGIN="123 Your Street, North Parramatta NSW 2151"
TRAFFIC_ROUTE_1_DESTINATION="456 Work Street, Sydney NSW 2000"
TRAFFIC_ROUTE_1_SCHEDULE="Mon-Fri 07:00-09:00"

# Route 2: Evening Commute
TRAFFIC_ROUTE_2_NAME="Evening Commute"
TRAFFIC_ROUTE_2_ORIGIN="456 Work Street, Sydney NSW 2000"
TRAFFIC_ROUTE_2_DESTINATION="123 Your Street, North Parramatta NSW 2151"
TRAFFIC_ROUTE_2_SCHEDULE="Mon-Fri 17:00-19:00"

# Route 3: Weekend Trip
TRAFFIC_ROUTE_3_NAME="Beach Trip"
TRAFFIC_ROUTE_3_ORIGIN="123 Your Street, North Parramatta NSW"
TRAFFIC_ROUTE_3_DESTINATION="Bondi Beach NSW"
TRAFFIC_ROUTE_3_SCHEDULE="Sat-Sun 09:00-18:00"
```

### Address Format

Use full addresses for best accuracy:
- ✅ Good: "123 Church Street, North Parramatta NSW 2151"
- ✅ Good: "Sydney Opera House, Sydney NSW"
- ⚠️ Okay: "North Parramatta" (less accurate)
- ❌ Bad: "Home" (won't work)

### How Scheduling Works

Routes only appear on the dashboard during their scheduled times:
- Morning commute shows 7-9am on weekdays
- Evening commute shows 5-7pm on weekdays
- Routes outside schedule don't appear (saves API calls)

### Check Active Routes

Test which routes are currently active:

```bash
curl http://localhost:5000/api/traffic/active-routes
```

**Example Response**:
```json
{
  "routes": [
    {
      "name": "Morning Commute",
      "origin": "123 Your Street, North Parramatta NSW 2151",
      "destination": "456 Work Street, Sydney NSW 2000",
      "route_num": 1,
      "schedule": "Mon-Fri 07:00-09:00"
    }
  ],
  "count": 1,
  "updated": "2025-10-27T08:30:00.123456"
}
```

## Google Calendar Configuration

### Get iCal URL

1. Open Google Calendar
2. Click settings (gear icon) → Settings
3. Select your calendar from the left
4. Scroll to "Integrate calendar"
5. Copy "Secret address in iCal format"
6. Add to .env:
   ```bash
   GOOGLE_CALENDAR_ICAL_URL=https://calendar.google.com/calendar/ical/.../basic.ics
   ```

### Privacy Note

The iCal URL is private but not secured. Anyone with the URL can view your calendar. To reset:
1. Go to calendar settings
2. Click "Reset" next to the iCal URL
3. Update .env with new URL

## API Keys

### Transport NSW API Key

1. Go to https://opendata.transport.nsw.gov.au/
2. Create an account
3. Create an app
4. Copy the API key
5. Add to .env:
   ```bash
   TRANSPORT_NSW_API_KEY=your_api_key_here
   ```

**Free tier**: 10,000 requests/month

### TomTom API Key

1. Go to https://developer.tomtom.com/
2. Create an account
3. Create an app (select Maps SDK)
4. Copy the API key
5. Add to .env:
   ```bash
   TOMTOM_API_KEY=your_tomtom_api_key_here
   ```

**Free tier**: 2,500 requests/day

## Testing

### Test Transport Departures

```bash
# Replace YOUR_STOP_ID with actual stop ID
curl http://localhost:5000/api/transport/departures/YOUR_STOP_ID
```

**Example Response**:
```json
{
  "stopId": "10101323",
  "departures": [
    {
      "destination": "Hornsby via Gordon",
      "line": "T1 North Shore & Western Line",
      "platform": "Platform 1",
      "time": "2025-10-27T08:17:00Z",
      "realtime": true,
      "delay_minutes": 0
    }
  ],
  "updated": "2025-10-27T08:15:30.123456"
}
```

### Test Traffic Route

```bash
curl "http://localhost:5000/api/traffic/route?origin=North+Parramatta&destination=Sydney"
```

**Example Response**:
```json
{
  "origin": "North Parramatta",
  "destination": "Sydney",
  "travelTimeMinutes": 35,
  "trafficDelayMinutes": 5,
  "distanceKm": 24.5,
  "status": "moderate",
  "updated": "2025-10-27T08:30:00.123456"
}
```

### Test Active Routes

```bash
curl http://localhost:5000/api/traffic/active-routes
```

## Troubleshooting

### Transport departures not showing

**Symptoms**: Widget shows error or no data

**Solutions**:
- Verify stop ID is correct (check URL at transportnsw.info)
- Check API key in .env: `TRANSPORT_NSW_API_KEY`
- Test directly: `curl http://localhost:5000/api/transport/departures/YOUR_STOP_ID`
- Check logs: `docker logs homepage-api`
- Verify API key is valid (check opendata.transport.nsw.gov.au)

### Traffic not showing

**Symptoms**: Widget shows no traffic data

**Solutions**:
- Verify TomTom API key in .env
- Check address format (use full addresses)
- Verify route is within schedule (test active-routes endpoint)
- Test manually: `curl "http://localhost:5000/api/traffic/route?origin=ADDRESS1&destination=ADDRESS2"`
- Check TomTom API quota (free tier: 2,500 requests/day)
- Check logs: `docker logs homepage-api`

### Calendar not showing

**Symptoms**: Calendar widget shows no events

**Solutions**:
- Verify iCal URL is correct (should start with https://calendar.google.com)
- Make sure calendar is not private/deleted
- Test URL in browser (should download .ics file)
- Check Homepage logs: `docker logs homepage`
- Try regenerating the iCal URL in Google Calendar settings

### Wrong schedule

**Symptoms**: Routes showing at wrong times

**Solutions**:
- Use 24-hour format: `07:00` not `7:00 AM`
- Days are case-insensitive: `mon-fri` or `Mon-Fri` both work
- Check server time: `docker exec homepage-api date`
- Verify timezone is set correctly in docker-compose
- Restart Homepage after .env changes: `docker compose -f docker-compose.dashboard.yml restart homepage`

### 503 Service Unavailable

**Symptoms**: API returns 503 error

**Causes**:
- Missing API key in environment
- API key not configured in .env

**Solutions**:
- Check .env file has all required keys
- Restart services after updating .env
- Test health endpoint: `curl http://localhost:5000/api/health`

## Widget Configuration

### Transport Widget Example

In `services.yaml`:

```yaml
- Train Departures:
    icon: mdi-train
    description: North Parramatta Station
    widget:
      type: customapi
      url: http://homepage-api:5000/api/transport/departures/10101323
      refreshInterval: 60000  # 1 minute
      mappings:
        - field: departures.0.destination
          label: Next Train
        - field: departures.0.time
          label: Departs
          format: relativeDate
        - field: departures.1.time
          label: Following
          format: relativeDate
```

### Traffic Widget Example

```yaml
- Morning Commute:
    icon: mdi-car
    description: To Work
    widget:
      type: customapi
      url: http://homepage-api:5000/api/traffic/route
      method: GET
      params:
        origin: "123 Home St, Parramatta NSW"
        destination: "456 Work St, Sydney NSW"
      refreshInterval: 300000  # 5 minutes
      mappings:
        - field: travelTimeMinutes
          label: Drive Time
          suffix: " min"
        - field: trafficDelayMinutes
          label: Delay
          suffix: " min"
        - field: status
          label: Traffic
```

### Calendar Widget Example

```yaml
- Google Calendar:
    icon: google-calendar.png
    href: https://calendar.google.com
    description: Upcoming events
    widget:
      type: calendar
      integrations:
        - type: ical
          url: https://calendar.google.com/calendar/ical/.../basic.ics
          name: Personal Calendar
          color: blue
          maxEvents: 5
```

## Refresh Intervals

Recommended refresh intervals:
- **Transport**: 60000ms (1 minute) - Departures change frequently
- **Traffic**: 300000ms (5 minutes) - Traffic updates gradually
- **Calendar**: 3600000ms (1 hour) - Events don't change often

Lower intervals = more API calls = higher quota usage

## Best Practices

### API Quota Management

1. **Transport NSW**: 10,000 requests/month
   - 1 widget × 60 requests/hour = 1,440 requests/day
   - ~43,200 requests/month per widget
   - Limit to 1-2 transport widgets

2. **TomTom**: 2,500 requests/day
   - 1 widget × 12 requests/hour = 288 requests/day
   - Can run 5-8 traffic widgets comfortably

3. **Use scheduling**: Only show routes when needed
   - Morning commute: 7-9am only
   - Evening commute: 5-7pm only
   - Saves ~75% of API calls

### Security

- Never commit .env file to git
- Keep API keys private
- Rotate keys if exposed
- Use restrictive CORS if exposing API publicly
- iCal URLs are semi-public (anyone with URL can view)

### Performance

- Use longer refresh intervals when possible
- Schedule routes to reduce unnecessary API calls
- Monitor API quota usage in provider dashboards
- Cache responses when data doesn't change often

## Support

- Transport NSW API: https://opendata.transport.nsw.gov.au/
- TomTom Support: https://developer.tomtom.com/support
- Homepage Docs: https://gethomepage.dev/
- Report issues: https://github.com/josephradford/home-server-stack/issues
