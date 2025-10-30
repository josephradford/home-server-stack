# Ticket 03: Home Assistant Setup

**Status**: ✅ Completed
**Completed**: 2025-10-30

## Implementation Summary

Successfully deployed Home Assistant as a core service for location tracking and home automation.

### What Was Implemented

1. **Docker Service** (`docker-compose.yml`):
   - Added Home Assistant container with bridge networking
   - Configured Traefik routing at `https://home.${DOMAIN}` with SSL (admin-secure middleware)
   - Set up health checks with 120s start period
   - Port 8123 exposed for direct access
   - Privileged mode enabled for device access

2. **Configuration Files** (`data/homeassistant/`):
   - Created `configuration.yaml` with default config, zones, and recorder settings
   - Created `secrets.yaml.example` template for sensitive values
   - Created empty automation files (automations.yaml, scripts.yaml, scenes.yaml)
   - Configured trusted proxies for Traefik integration (Docker networks + local network)
   - **IMPORTANT**: Must trust 172.16.0.0/12 (Docker) and 192.168.0.0/16 (local) for Traefik access
   - Set database purge to 30 days to control size

3. **Homepage Dashboard** (`config/homepage/services-template.yaml`):
   - Added "Family & Location" section with Home Assistant widget
   - Configured homeassistant widget type with API token
   - Added Family Map link to map view
   - Included container stats monitoring (CPU, memory, network)
   - Placeholder for person entities (added in Ticket 09)

4. **Environment Variables** (`.env.example`):
   - Enhanced HOMEASSISTANT_URL documentation (default: http://homeassistant:8123)
   - Added comprehensive HOMEASSISTANT_TOKEN instructions with token generation steps
   - Explained internal container communication setup

5. **Documentation**:
   - Created comprehensive `docs/HOME_ASSISTANT_SETUP.md` guide
   - Added Home Assistant section to `docs/DASHBOARD_SETUP.md`
   - Documented onboarding wizard steps
   - Included API token generation process
   - Added troubleshooting for common issues
   - Referenced Ticket 09 for iOS Companion App setup

### Key Decisions

1. **Bridge Network vs Host Mode**:
   - Used bridge networking for consistency with stack architecture
   - Enables Traefik reverse proxy with SSL
   - Trade-off: Some device discovery features limited (mDNS, SSDP)
   - Note: Can switch to host mode if needed for specific integrations

2. **Core Service Placement**:
   - Added to `docker-compose.yml` (not dashboard.yml) as it's a core service
   - Home Assistant used for more than just dashboard (location tracking, automation)
   - Aligns with service categorization in stack

3. **Security Configuration**:
   - Applied `admin-secure-no-ratelimit` middleware (VPN/local access only)
   - No rate limiting to accommodate widget API calls
   - Private by default (location tracking is sensitive)

4. **Database Management**:
   - Set 30-day retention in recorder
   - Prevents unbounded database growth
   - Configurable for different retention needs

### Testing Performed

- ✅ Container configuration validated with `make validate`
- ✅ Service definition follows stack patterns (Traefik labels, networks)
- ✅ Configuration files use correct YAML syntax
- ✅ Homepage widget configuration matches Homepage documentation
- ✅ Environment variables properly documented

### Known Issues & Fixes

**Issue**: 400 Bad Request when accessing via `https://home.${DOMAIN}` (direct access via IP:8123 works)

**Cause**: Home Assistant requires explicit trust of reverse proxy networks. The initial configuration only trusted localhost.

**Fix**: Update `data/homeassistant/configuration.yaml` after first deployment:
```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - ::1
    - 172.16.0.0/12  # Docker bridge networks
    - 192.168.0.0/16  # Local network range
```

Then restart: `docker restart homeassistant`

This is now documented in the troubleshooting section of `docs/HOME_ASSISTANT_SETUP.md`.

### Next Steps

- Deploy to server and complete onboarding wizard
- Generate API token and add to .env
- Configure iOS Companion App (Ticket 09)
- Set up person tracking and device tracking
- Create location-based automations
- Integrate with n8n workflows

---

## Original Ticket Content

## Objective
Deploy Home Assistant for location tracking and device monitoring.

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
- Apple Health fitness data export

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
- [x] Home Assistant container added to docker-compose.yml (core service)
- [x] Initial configuration.yaml created with zones
- [x] Configuration uses bridge networking for Traefik integration
- [x] Homepage widget configured in services-template.yaml
- [x] Environment variables documented in .env.example
- [x] Comprehensive documentation created (HOME_ASSISTANT_SETUP.md)
- [x] Dashboard setup guide updated with Home Assistant section

## Testing
```bash
# Validate configuration
make validate

# Start Home Assistant
make start

# Check startup logs
docker logs -f homeassistant

# Wait for "Home Assistant is running"
# Then access http://SERVER_IP:8123

# Verify API connection (after onboarding and token generation)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://SERVER_IP:8123/api/
```

## Dependencies
- Ticket 01: Project structure ✅
- Ticket 02: Homepage dashboard ✅

## Notes
- First startup takes 60-120 seconds
- Bridge networking used for Traefik integration (not host mode)
- Token must be added to .env after generation
- Person tracking configured separately in Ticket 09
- Keep purge_keep_days reasonable to control database size
- Habitica integration is future work (Tickets 11 & 12)
