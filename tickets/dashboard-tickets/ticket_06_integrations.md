# Ticket 06: Transport, Calendar & Traffic Widgets

## Objective
Configure Homepage widgets for Transport NSW departures, Google Calendar, and traffic conditions with dynamic route scheduling.

## Tasks

### 1. Update services.yaml - Transport & Commute Section

Update `data/homepage/config/services.yaml`:

```yaml
- Transport & Commute:
    - Train Departures:
        icon: {{HOMEPAGE_VAR_TRANSPORT_STOP_1_ICON:-mdi-train}}
        description: {{HOMEPAGE_VAR_TRANSPORT_STOP_1_NAME:-North Parramatta Station}}
        widget:
          type: customapi
          url: http://homepage-api:5000/api/transport/departures/{{HOMEPAGE_VAR_TRANSPORT_STOP_1_ID}}
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

    - Bus Departures:
        icon: {{HOMEPAGE_VAR_TRANSPORT_STOP_2_ICON:-mdi-bus}}
        description: {{HOMEPAGE_VAR_TRANSPORT_STOP_2_NAME:-Bus Stop}}
        widget:
          type: customapi
          url: http://homepage-api:5000/api/transport/departures/{{HOMEPAGE_VAR_TRANSPORT_STOP_2_ID}}
          refreshInterval: 60000
          mappings:
            - field: departures.0.destination
              label: Next Bus
            - field: departures.0.time
              label: Departs
              format: relativeDate

    - Morning Commute:
        icon: mdi-car
        description: {{HOMEPAGE_VAR_TRAFFIC_ROUTE_1_NAME:-To Work}}
        widget:
          type: customapi
          url: http://homepage-api:5000/api/traffic/route
          method: GET
          params:
            origin: {{HOMEPAGE_VAR_TRAFFIC_ROUTE_1_ORIGIN}}
            destination: {{HOMEPAGE_VAR_TRAFFIC_ROUTE_1_DESTINATION}}
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
              remap:
                - value: clear
                  to: "✅ Clear"
                - value: moderate
                  to: "🟡 Moderate"
                - value: heavy
                  to: "🔴 Heavy"

    - Evening Commute:
        icon: mdi-home-import-outline
        description: {{HOMEPAGE_VAR_TRAFFIC_ROUTE_2_NAME:-To Home}}
        widget:
          type: customapi
          url: http://homepage-api:5000/api/traffic/route
          method: GET
          params:
            origin: {{HOMEPAGE_VAR_TRAFFIC_ROUTE_2_ORIGIN}}
            destination: {{HOMEPAGE_VAR_TRAFFIC_ROUTE_2_DESTINATION}}
          refreshInterval: 300000
          mappings:
            - field: travelTimeMinutes
              label: Drive Time
              suffix: " min"
            - field: trafficDelayMinutes
              label: Delay
              suffix: " min"
            - field: status
              label: Traffic

    - Transport NSW:
        icon: mdi-bus-multiple
        href: https://transportnsw.info/
        description: View all services
```

### 2. Update services.yaml - Calendar & Tasks Section

Add to `data/homepage/config/services.yaml`:

```yaml
- Calendar & Tasks:
    - Google Calendar:
        icon: google-calendar.png
        href: https://calendar.google.com
        description: Upcoming events
        widget:
          type: calendar
          integrations:
            - type: ical
              url: {{HOMEPAGE_VAR_GCAL_ICAL_URL}}
              name: Personal Calendar
              color: blue
              maxEvents: 5

    - BOM Weather:
        icon: mdi-weather-partly-cloudy
        href: http://www.bom.gov.au/places/nsw/north-parramatta/
        description: Detailed forecast
        widget:
          type: customapi
          url: http://homepage-api:5000/api/bom/weather
          refreshInterval: 300000  # 5 minutes
          mappings:
            - field: current.temp
              label: Temperature
              suffix: "°C"
            - field: current.apparent_temp
              label: Feels Like
              suffix: "°C"
            - field: current.humidity
              label: Humidity
              suffix: "%"
            - field: current.description
              label: Conditions
```

### 3. Create Traffic Route Scheduler Script

Create `homepage-api/traffic_scheduler.py`:

```python
"""
Traffic route scheduler for Homepage
Determines which routes to show based on schedule configuration
"""

from datetime import datetime
import os
import re

def parse_schedule(schedule_string):
    """
    Parse schedule string like "Mon-Fri 07:00-09:00"
    Returns: (days, start_time, end_time)
    """
    if not schedule_string:
        return None
    
    # Parse format: "Mon-Fri 07:00-09:00" or "Daily 00:00-23:59"
    pattern = r'([\w-]+)\s+(\d{2}:\d{2})-(\d{2}:\d{2})'
    match = re.match(pattern, schedule_string)
    
    if not match:
        return None
    
    days_str, start_time, end_time = match.groups()
    
    # Parse days
    if days_str.lower() == 'daily':
        days = list(range(7))  # 0-6 (Monday-Sunday)
    elif '-' in days_str:
        # Parse "Mon-Fri"
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        start_day, end_day = days_str.lower().split('-')
        start_idx = day_map.get(start_day, 0)
        end_idx = day_map.get(end_day, 4)
        days = list(range(start_idx, end_idx + 1))
    else:
        # Single day
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        days = [day_map.get(days_str.lower(), 0)]
    
    return days, start_time, end_time


def is_route_active(schedule_string):
    """
    Check if route should be shown based on schedule
    """
    if not schedule_string:
        return True  # Always show if no schedule
    
    parsed = parse_schedule(schedule_string)
    if not parsed:
        return True
    
    days, start_time, end_time = parsed
    
    now = datetime.now()
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_time = now.strftime('%H:%M')
    
    # Check if current day is in schedule
    if current_day not in days:
        return False
    
    # Check if current time is in range
    if start_time <= current_time <= end_time:
        return True
    
    return False


def get_active_routes():
    """
    Get list of active traffic routes based on schedule
    Returns list of route configurations
    """
    active_routes = []
    
    # Check each configured route
    route_num = 1
    while True:
        route_name = os.getenv(f'TRAFFIC_ROUTE_{route_num}_NAME')
        if not route_name:
            break
        
        schedule = os.getenv(f'TRAFFIC_ROUTE_{route_num}_SCHEDULE', 'Daily 00:00-23:59')
        
        if is_route_active(schedule):
            active_routes.append({
                'name': route_name,
                'origin': os.getenv(f'TRAFFIC_ROUTE_{route_num}_ORIGIN'),
                'destination': os.getenv(f'TRAFFIC_ROUTE_{route_num}_DESTINATION'),
                'route_num': route_num
            })
        
        route_num += 1
    
    return active_routes
```

### 4. Add Active Routes Endpoint to app.py

Add to `homepage-api/app.py`:

```python
from traffic_scheduler import get_active_routes, is_route_active

@app.route('/api/traffic/active-routes')
def active_routes():
    """Get list of currently active traffic routes based on schedule"""
    try:
        routes = get_active_routes()
        return jsonify({
            'routes': routes,
            'count': len(routes),
            'updated': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### 5. Create Configuration Documentation

Create `docs/TRANSPORT_TRAFFIC_CONFIG.md`:

```markdown
# Transport & Traffic Configuration

## Transport Stop Configuration

### Finding Stop IDs

1. Go to https://transportnsw.info/
2. Search for your station or stop
3. Click on it
4. Copy the stop ID from the URL

Example URL: `https://transportnsw.info/stop?q=10101323`
Stop ID: `10101323`

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

### Icons

Available icons from Material Design Icons:
- `mdi-train` - Train
- `mdi-bus` - Bus
- `mdi-ferry` - Ferry
- `mdi-tram` - Light rail
- `mdi-subway` - Metro

## Traffic Route Configuration

### Schedule Format

Format: `DAYS START_TIME-END_TIME`

Examples:
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

## Troubleshooting

### Transport departures not showing
- Verify stop ID is correct
- Check API key in .env
- Test directly: `curl http://localhost:5000/api/transport/departures/YOUR_STOP_ID`
- Check logs: `docker logs homepage-api`

### Traffic not showing
- Verify TomTom API key
- Check address format (use full addresses)
- Verify route is within schedule
- Test: `curl "http://localhost:5000/api/traffic/route?origin=ADDRESS1&destination=ADDRESS2"`

### Calendar not showing
- Verify iCal URL is correct (should start with https://calendar.google.com)
- Make sure calendar is not private/deleted
- Check Homepage logs: `docker logs homepage`

### Wrong schedule
- Use 24-hour format: `07:00` not `7:00 AM`
- Days are case-insensitive: `mon-fri` or `Mon-Fri` both work
- Restart Homepage after .env changes: `docker compose -f docker-compose.dashboard.yml restart homepage`
```

### 6. Update Homepage Environment Variables

Update docker-compose.dashboard.yml homepage service:

```yaml
    environment:
      # ... existing vars ...
      # Transport stops (add dynamically in startup script)
      HOMEPAGE_VAR_TRANSPORT_STOP_1_ID: ${TRANSPORT_STOP_1_ID}
      HOMEPAGE_VAR_TRANSPORT_STOP_1_NAME: ${TRANSPORT_STOP_1_NAME}
      HOMEPAGE_VAR_TRANSPORT_STOP_1_ICON: ${TRANSPORT_STOP_1_ICON}
      HOMEPAGE_VAR_TRANSPORT_STOP_2_ID: ${TRANSPORT_STOP_2_ID}
      HOMEPAGE_VAR_TRANSPORT_STOP_2_NAME: ${TRANSPORT_STOP_2_NAME}
      HOMEPAGE_VAR_TRANSPORT_STOP_2_ICON: ${TRANSPORT_STOP_2_ICON}
      # Traffic routes
      HOMEPAGE_VAR_TRAFFIC_ROUTE_1_NAME: ${TRAFFIC_ROUTE_1_NAME}
      HOMEPAGE_VAR_TRAFFIC_ROUTE_1_ORIGIN: ${TRAFFIC_ROUTE_1_ORIGIN}
      HOMEPAGE_VAR_TRAFFIC_ROUTE_1_DESTINATION: ${TRAFFIC_ROUTE_1_DESTINATION}
      HOMEPAGE_VAR_TRAFFIC_ROUTE_2_NAME: ${TRAFFIC_ROUTE_2_NAME}
      HOMEPAGE_VAR_TRAFFIC_ROUTE_2_ORIGIN: ${TRAFFIC_ROUTE_2_ORIGIN}
      HOMEPAGE_VAR_TRAFFIC_ROUTE_2_DESTINATION: ${TRAFFIC_ROUTE_2_DESTINATION}
```

## Acceptance Criteria
- [ ] Transport widgets configured in services.yaml
- [ ] Calendar widget configured with iCal support
- [ ] Traffic widgets configured with dynamic routes
- [ ] Traffic scheduler script created
- [ ] Active routes endpoint added to API
- [ ] All widgets use environment variables
- [ ] Documentation created for configuration
- [ ] Multiple stops/routes supported
- [ ] Schedule-based route display working
- [ ] Icons and labels configurable

## Testing
```bash
# Test transport API
curl http://localhost:5000/api/transport/departures/YOUR_STOP_ID

# Test traffic API
curl "http://localhost:5000/api/traffic/route?origin=North+Parramatta&destination=Sydney"

# Test active routes
curl http://localhost:5000/api/traffic/active-routes

# Check Homepage
# Visit http://SERVER_IP:3100
# Verify all widgets display correctly
```

## Dependencies
- Ticket 02: Homepage dashboard
- Ticket 05: Backend API
- Transport NSW API key configured
- TomTom API key configured
- Google Calendar iCal URL configured

## Notes
- Transport widgets refresh every 1 minute
- Traffic widgets refresh every 5 minutes
- Calendar shows next 5 events
- Routes only show during scheduled times
- Use full addresses for traffic accuracy
- Multiple stops and routes supported via environment variables
- Add STOP_3, STOP_4, ROUTE_3, etc. as needed
