# Ticket 01: Project Structure and Documentation

## Objective
Set up the project structure for the Homepage Dashboard integration with necessary directories and documentation.

## Tasks

### 1. Create Directory Structure
```bash
home-server-stack/
├── docker-compose.dashboard.yml
├── homepage-api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── habitica/
│   ├── config/
│   └── docker-compose.habitica.yml
├── data/
│   ├── homepage/
│   │   └── config/
│   │       ├── services.yaml
│   │       ├── widgets.yaml
│   │       ├── settings.yaml
│   │       ├── docker.yaml
│   │       └── bookmarks.yaml (optional)
│   ├── homeassistant/
│   ├── habitica/
│   │   ├── mongo/
│   │   └── redis/
│   └── homepage-api/
└── ssl/
    ├── habitica/
    └── (existing certs)
```

### 2. Update .env.example
Add these new variables to `.env.example`:

```bash
# =============================================================================
# DASHBOARD CONFIGURATION
# =============================================================================

# Server Configuration (existing)
SERVER_IP=192.168.1.100
PUID=1000
PGID=1000
TIMEZONE=Australia/Sydney

# =============================================================================
# TRANSPORT NSW
# =============================================================================
# Get your API key from: https://opendata.transport.nsw.gov.au/
TRANSPORTNSW_API_KEY=your_api_key_here

# Transport Stop IDs (find at https://transportnsw.info/)
# North Parramatta Station - Platform 1 (Example)
TRANSPORT_STOP_1_ID=10101323
TRANSPORT_STOP_1_NAME="North Parra Platform 1"
TRANSPORT_STOP_1_ICON=mdi-train

# North Parramatta Bus Stop (Example)
TRANSPORT_STOP_2_ID=2093XX
TRANSPORT_STOP_2_NAME="Bus Stop - Church St"
TRANSPORT_STOP_2_ICON=mdi-bus

# Add more stops as needed (STOP_3, STOP_4, etc.)

# =============================================================================
# GOOGLE CALENDAR
# =============================================================================
# Get iCal URL from: Google Calendar > Settings > Integrate calendar
GOOGLE_CALENDAR_ICAL_URL=https://calendar.google.com/calendar/ical/xxxxx/basic.ics

# =============================================================================
# TRAFFIC MONITORING (TomTom API)
# =============================================================================
# Get your API key from: https://developer.tomtom.com/
TOMTOM_API_KEY=your_tomtom_api_key_here

# Traffic Routes Configuration
# Route 1: Morning Commute
TRAFFIC_ROUTE_1_NAME="Morning Commute"
TRAFFIC_ROUTE_1_ORIGIN="123 Your Street, North Parramatta NSW 2151"
TRAFFIC_ROUTE_1_DESTINATION="456 Work Street, Sydney NSW 2000"
TRAFFIC_ROUTE_1_SCHEDULE="Mon-Fri 07:00-09:00"  # When to show this route

# Route 2: Evening Commute  
TRAFFIC_ROUTE_2_NAME="Evening Commute"
TRAFFIC_ROUTE_2_ORIGIN="456 Work Street, Sydney NSW 2000"
TRAFFIC_ROUTE_2_DESTINATION="123 Your Street, North Parramatta NSW 2151"
TRAFFIC_ROUTE_2_SCHEDULE="Mon-Fri 17:00-19:00"

# Add more routes as needed (ROUTE_3, ROUTE_4, etc.)

# =============================================================================
# HOME ASSISTANT
# =============================================================================
HOMEASSISTANT_URL=http://homeassistant:8123
# Token will be generated after HA first setup

# =============================================================================
# HABITICA (SELF-HOSTED)
# =============================================================================
# Admin Configuration
HABITICA_ADMIN_EMAIL=your@email.com
HABITICA_ADMIN_PASSWORD=secure_password_here

# Database
HABITICA_MONGO_USER=habitica
HABITICA_MONGO_PASSWORD=secure_mongo_password
HABITICA_DB_NAME=habitica

# Session Secret (generate with: openssl rand -base64 32)
HABITICA_SESSION_SECRET=your_session_secret_here

# Base URL for HTTPS access
HABITICA_BASE_URL=https://habitica.yourdomain.local

# API Credentials (generated after setup)
HABITICA_USER_ID=
HABITICA_API_TOKEN=

# =============================================================================
# EXISTING SERVICES (from your current setup)
# =============================================================================
ADGUARD_USER=admin
ADGUARD_PASS=your_password

GRAFANA_USER=admin
GRAFANA_PASS=your_password

N8N_PASSWORD=your_password
N8N_EDITOR_BASE_URL=https://your-domain.ddns.net:5678
```

### 3. Create README.md for Dashboard
Create `docs/DASHBOARD_SETUP.md`:

```markdown
# Dashboard Setup Guide

This guide covers setting up the Homepage dashboard with Home Assistant, Habitica, and various integrations.

## Quick Start

1. Copy environment variables:
   ```bash
   cp .env.example .env
   nano .env  # Fill in your values
   ```

2. Get required API keys:
   - Transport NSW: https://opendata.transport.nsw.gov.au/
   - TomTom Traffic: https://developer.tomtom.com/
   - Google Calendar: Get iCal URL from calendar settings

3. Deploy services:
   ```bash
   docker compose -f docker-compose.dashboard.yml up -d
   ```

4. Access services:
   - Homepage: http://SERVER_IP:3100
   - Home Assistant: http://SERVER_IP:8123
   - Habitica: https://SERVER_IP:3000

## Configuration

See individual tickets for detailed setup:
- Ticket 02: Homepage Dashboard
- Ticket 03: Home Assistant
- Ticket 04: Self-hosted Habitica
- Ticket 05: Backend API
- etc.

## Transport Stop IDs

Find your stop IDs:
1. Go to https://transportnsw.info/
2. Search for your station/stop
3. Click on it
4. Copy the ID from the URL (usually 8 digits)

## Traffic Routes

Configure multiple routes with schedules:
- Routes only show during scheduled times
- Use full addresses for accuracy
- Schedule format: "Mon-Fri 07:00-09:00" or "Daily 00:00-23:59"
```

### 4. Update Main README
Add a new section to the main `README.md`:

```markdown
## Dashboard & Automation

This stack includes a comprehensive dashboard with location tracking, habit tracking, and integrations:

- **Homepage**: Unified dashboard for all services
- **Home Assistant**: Automation hub and location tracking
- **Habitica**: Self-hosted gamified task manager
- **Backend API**: Custom integrations for BOM weather, Transport NSW, traffic

### Deploy Dashboard Services

```bash
docker compose -f docker-compose.dashboard.yml up -d
```

See [Dashboard Setup Guide](docs/DASHBOARD_SETUP.md) for detailed instructions.

### Features

- 🌤️ Australian BOM weather for North Parramatta
- 📅 Google Calendar integration
- 🚊 Real-time Transport NSW departures
- 🚗 Traffic conditions for configurable routes
- 📍 Family location tracking via iOS/Android
- 🎮 Habitica fitness automation (Apple Watch workouts)
- 🐳 Docker container monitoring
```

## Acceptance Criteria
- [ ] All directories created with proper permissions
- [ ] .env.example updated with all new variables
- [ ] DASHBOARD_SETUP.md created with comprehensive instructions
- [ ] Main README.md updated with dashboard section
- [ ] Directory structure matches the plan

## Dependencies
None - this is the first ticket

## Notes
- Ensure all directories have correct ownership (PUID:PGID)
- SSL certificates directory for Habitica HTTPS
- Keep structure consistent with existing repo style
