# Ticket 03: Home Assistant Setup

## Objective
Deploy Home Assistant for location tracking, iCloud device monitoring, and Habitica integration.

## Tasks

### 1. Add Home Assistant to docker-compose.dashboard.yml

Add to `docker-compose.dashboard.yml`:

```yaml
  homeassistant:
    container_name: homeassistant
    image: ghcr.io/home-assistant/home-assistant:stable
    volumes:
      - ./data/homeassistant:/config
      - /etc/localtime:/etc/localtime:ro
      - /run/dbus:/run/dbus:ro
    environment:
      - TZ=Australia/Sydney
    ports:
      - "8123:8123"
    restart: unless-stopped
    privileged: true
    network_mode: host
```

### 2. Create Home Assistant Initial Configuration

Create `data/homeassistant/configuration.yaml`:

```yaml
# Home Assistant Configuration
default_config:

# Text to speech
tts:
  - platform: google_translate

# Automation configuration
automation: !include automations.yaml
script: !include scripts.yaml
scene: !include scenes.yaml

# HTTP Configuration
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - ::1

# Recorder - limit database size
recorder:
  purge_keep_days: 30
  commit_interval: 30

# Logger
logger:
  default: info
  logs:
    homeassistant.components.habitica: debug

# Zones
zone:
  - name: Home
    latitude: -33.8000
    longitude: 151.0000
    radius: 100
    icon: mdi:home

  - name: Work
    latitude: !secret work_latitude
    longitude: !secret work_longitude
    radius: 200
    icon: mdi:office-building
```

### 3. Create secrets.yaml Template

Create `data/homeassistant/secrets.yaml.example`:

```yaml
# Home Assistant Secrets
# Copy this to secrets.yaml and fill in your values

# Work location (optional)
work_latitude: -33.8688
work_longitude: 151.2093

# Additional zones (optional)
# Add more as needed
```

### 4. Create Empty Automation Files

```bash
# Create empty files for Home Assistant to populate
touch data/homeassistant/automations.yaml
touch data/homeassistant/scripts.yaml
touch data/homeassistant/scenes.yaml
```

### 5. Update Homepage services.yaml

Add to `data/homepage/config/services.yaml` under "Family & Location":

```yaml
- Family & Location:
    - Home Assistant:
        icon: home-assistant.png
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:8123
        description: Location & Automation Hub
        widget:
          type: homeassistant
          url: {{HOMEPAGE_VAR_HOMEASSISTANT_URL}}
          key: {{HOMEPAGE_VAR_HOMEASSISTANT_TOKEN}}
          custom:
            - state: sensor.homeassistant_version
              label: Version
              field: state

    - Family Map:
        icon: mdi-map-marker-multiple
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:8123/lovelace/map
        description: View all locations

    # Person entities will be added after iOS app setup
    # See Ticket 09 for iOS Companion App configuration
```

### 6. Create Home Assistant Setup Documentation

Create `docs/HOME_ASSISTANT_SETUP.md`:

```markdown
# Home Assistant Setup Guide

## Initial Setup

1. Start Home Assistant:
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d homeassistant
   ```

2. Wait for startup (60-120 seconds):
   ```bash
   docker logs -f homeassistant
   ```

3. Access Home Assistant at http://SERVER_IP:8123

4. Complete onboarding wizard:
   - Create admin account
   - Set location to North Parramatta, NSW
   - Name your home
   - Skip device discovery for now

## Generate API Token

1. Click on your profile (bottom left)
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"
4. Name it "Homepage Dashboard"
5. Copy the token
6. Add to `.env`:
   ```bash
   HOMEASSISTANT_TOKEN=your_token_here
   ```
7. Restart Homepage:
   ```bash
   docker compose -f docker-compose.dashboard.yml restart homepage
   ```

## iOS Companion App Setup

See **Ticket 09** for detailed iOS app configuration including:
- Location tracking
- Device tracking (AirPods, iPads, etc.)
- Sensor configuration

## Habitica Integration

See **Ticket 08** for Habitica integration setup.

## Apple Health Integration

See **Ticket 09** for Apple Health fitness data export.

## Troubleshooting

### Cannot access Home Assistant
- Check if port 8123 is open
- Verify container is running: `docker ps | grep homeassistant`
- Check logs: `docker logs homeassistant`

### Network mode issues
Home Assistant uses `network_mode: host` for device discovery. If this causes issues:
1. Switch to bridge network
2. Add to networks section in docker-compose
3. You may lose some discovery features

### Database growing too large
- Adjust `purge_keep_days` in configuration.yaml
- Exclude unnecessary entities from recorder
```

### 7. Update Main Dashboard Documentation

Add to `docs/DASHBOARD_SETUP.md`:

```markdown
## Home Assistant Setup

Home Assistant provides:
- Family location tracking via iOS/Android Companion App
- iCloud device tracking (AirPods, iPads, etc.)
- Habitica integration and automation
- Apple Health fitness data processing

### Quick Start

1. Deploy Home Assistant:
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d homeassistant
   ```

2. Complete initial setup at http://SERVER_IP:8123

3. Generate API token and add to .env

4. See [Home Assistant Setup Guide](HOME_ASSISTANT_SETUP.md) for details

### iOS Companion App

Install from App Store and configure for:
- Location tracking
- Device tracking
- Sensor data

Detailed instructions in **Ticket 09**.
```

## Acceptance Criteria
- [ ] Home Assistant container added to docker-compose.dashboard.yml
- [ ] Initial configuration.yaml created with zones
- [ ] Home Assistant accessible at http://SERVER_IP:8123
- [ ] Onboarding wizard completed
- [ ] API token generated and added to .env
- [ ] Home Assistant widget visible in Homepage
- [ ] Documentation created for setup process
- [ ] Network mode: host working correctly

## Testing
```bash
# Start Home Assistant
docker compose -f docker-compose.dashboard.yml up -d homeassistant

# Check startup logs
docker logs -f homeassistant

# Wait for "Home Assistant is running"
# Then access http://SERVER_IP:8123

# Verify API connection
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://SERVER_IP:8123/api/
```

## Dependencies
- Ticket 01: Project structure
- Ticket 02: Homepage dashboard

## Notes
- First startup takes 60-120 seconds
- Use `network_mode: host` for best device discovery
- Token must be added to .env after generation
- Person tracking configured separately in Ticket 09
- Habitica integration configured in Ticket 08
- Keep purge_keep_days reasonable to control database size
