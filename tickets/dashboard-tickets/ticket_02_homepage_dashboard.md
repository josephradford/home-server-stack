# Ticket 02: Homepage Dashboard Setup

## Objective
Set up the Homepage dashboard container with configuration files for displaying all services and integrations.

## Tasks

### 1. Create Homepage Service in docker-compose.dashboard.yml

Create `docker-compose.dashboard.yml`:

```yaml
version: '3.8'

services:
  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    environment:
      PUID: ${PUID:-1000}
      PGID: ${PGID:-1000}
      HOMEPAGE_ALLOWED_HOSTS: "${SERVER_IP},localhost,127.0.0.1"
      # Pass through environment variables for configs
      HOMEPAGE_VAR_SERVER_IP: ${SERVER_IP}
      HOMEPAGE_VAR_ADGUARD_USER: ${ADGUARD_USER}
      HOMEPAGE_VAR_ADGUARD_PASS: ${ADGUARD_PASS}
      HOMEPAGE_VAR_GRAFANA_USER: ${GRAFANA_USER:-admin}
      HOMEPAGE_VAR_GRAFANA_PASS: ${GRAFANA_PASS}
      HOMEPAGE_VAR_TRANSPORTNSW_KEY: ${TRANSPORTNSW_API_KEY}
      HOMEPAGE_VAR_GCAL_ICAL_URL: ${GOOGLE_CALENDAR_ICAL_URL}
      HOMEPAGE_VAR_HOMEASSISTANT_URL: ${HOMEASSISTANT_URL}
      HOMEPAGE_VAR_HOMEASSISTANT_TOKEN: ${HOMEASSISTANT_TOKEN}
      HOMEPAGE_VAR_HABITICA_URL: ${HABITICA_BASE_URL}
      HOMEPAGE_VAR_HABITICA_USER_ID: ${HABITICA_USER_ID}
      HOMEPAGE_VAR_HABITICA_API_TOKEN: ${HABITICA_API_TOKEN}
    ports:
      - "3100:3000"
    volumes:
      - ./data/homepage/config:/app/config
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /:/host:ro
    restart: unless-stopped
    networks:
      - home-server
    depends_on:
      - homepage-api

networks:
  home-server:
    name: home-server
    external: true
```

### 2. Create settings.yaml

Create `data/homepage/config/settings.yaml`:

```yaml
---
title: Home Server Dashboard
favicon: https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/home-assistant-alt.png

# Background configuration
background:
  image: https://images.unsplash.com/photo-1557683316-973673baf926
  blur: sm
  saturate: 50
  brightness: 50
  opacity: 50

theme: dark
color: slate

# Layout configuration
layout:
  Home Server:
    style: row
    columns: 4
  Transport & Commute:
    style: row
    columns: 2
  Family & Location:
    style: row
    columns: 3
  Calendar & Tasks:
    style: row
    columns: 2
  Habitica RPG:
    style: row
    columns: 3

# UI preferences
statusStyle: "dot"
showStats: false
hideVersion: true

# Quick launch
quicklaunch:
  searchDescriptions: true
  hideInternetSearch: false
  showSearchSuggestions: true
  hideVisitURL: false

# Header style
headerStyle: boxed
target: _blank
```

### 3. Create widgets.yaml

Create `data/homepage/config/widgets.yaml`:

```yaml
---
# Top bar widgets
- logo:
    icon: https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/home-assistant-alt.png

- search:
    provider: google
    target: _blank

- datetime:
    text_size: xl
    format:
      dateStyle: long
      timeStyle: short
      hour12: false

# Weather widget using OpenMeteo
- openmeteo:
    label: North Parramatta
    latitude: -33.8
    longitude: 151.0
    timezone: Australia/Sydney
    units: metric
    cache: 5

# System resources
- resources:
    label: Server
    expanded: false
    cpu: true
    memory: true
    disk: /
    uptime: true
```

### 4. Create docker.yaml

Create `data/homepage/config/docker.yaml`:

```yaml
---
# Docker socket configuration for container monitoring
my-docker:
  socket: /var/run/docker.sock
```

### 5. Create bookmarks.yaml (Optional)

Create `data/homepage/config/bookmarks.yaml`:

```yaml
---
- Quick Links:
    - Transport NSW:
        - abbr: TN
          href: https://transportnsw.info/
    - BOM Sydney:
        - abbr: BOM
          href: http://www.bom.gov.au/nsw/sydney/
    - Google Calendar:
        - abbr: GC
          href: https://calendar.google.com/

- Admin:
    - Router:
        - abbr: RT
          href: http://192.168.1.1/
          description: Home router admin
    - GitHub Repo:
        - abbr: GH
          href: https://github.com/josephradford/home-server-stack
          description: This repo
```

### 6. Create Initial services.yaml Structure

Create `data/homepage/config/services.yaml`:

```yaml
---
# Home Server Services
- Home Server:
    - AdGuard Home:
        icon: adguard-home.png
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:80
        description: Network-wide ad blocking
        widget:
          type: adguard
          url: http://{{HOMEPAGE_VAR_SERVER_IP}}
          username: {{HOMEPAGE_VAR_ADGUARD_USER}}
          password: {{HOMEPAGE_VAR_ADGUARD_PASS}}

    - n8n:
        icon: n8n.png
        href: https://{{HOMEPAGE_VAR_SERVER_IP}}:5678
        description: Workflow automation
        container: n8n

    - Ollama:
        icon: ollama.png
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:11434
        description: Local AI models
        container: ollama

    - Grafana:
        icon: grafana.png
        href: http://{{HOMEPAGE_VAR_SERVER_IP}}:3001
        description: Monitoring dashboards
        widget:
          type: grafana
          url: http://{{HOMEPAGE_VAR_SERVER_IP}}:3001
          username: {{HOMEPAGE_VAR_GRAFANA_USER}}
          password: {{HOMEPAGE_VAR_GRAFANA_PASS}}

# Placeholder sections - will be populated by other tickets
- Transport & Commute:
    # Will be added in Ticket 06

- Family & Location:
    # Will be added in Ticket 03

- Calendar & Tasks:
    # Will be added in Ticket 06

- Habitica RPG:
    # Will be added in Ticket 04
```

### 7. Create Setup Script

Create `scripts/setup-homepage.sh`:

```bash
#!/bin/bash
set -e

echo "🏠 Setting up Homepage Dashboard"
echo "================================"

# Create config directory
mkdir -p data/homepage/config

# Check if config files exist
if [ ! -f "data/homepage/config/settings.yaml" ]; then
    echo "⚠️  Config files not found. Please ensure all YAML files are in place."
    exit 1
fi

# Check Docker network
if ! docker network inspect home-server &>/dev/null; then
    echo "📡 Creating Docker network..."
    docker network create home-server
fi

echo "🚀 Starting Homepage..."
docker compose -f docker-compose.dashboard.yml up -d homepage

echo "✅ Homepage is running at http://$(grep SERVER_IP .env | cut -d '=' -f2):3100"
```

Make it executable:
```bash
chmod +x scripts/setup-homepage.sh
```

## Acceptance Criteria
- [ ] docker-compose.dashboard.yml created with Homepage service
- [ ] All YAML config files created in data/homepage/config/
- [ ] Setup script created and executable
- [ ] Homepage accessible at http://SERVER_IP:3100
- [ ] Docker containers visible in Homepage
- [ ] Existing services (AdGuard, n8n, Ollama, Grafana) displayed correctly
- [ ] Weather widget showing North Parramatta data
- [ ] System resources displayed

## Testing
```bash
# Test deployment
docker compose -f docker-compose.dashboard.yml up -d homepage

# Check logs
docker logs homepage

# Verify accessibility
curl http://localhost:3100
```

## Dependencies
- Ticket 01 completed (directory structure)
- Existing home-server Docker network
- .env file configured

## Notes
- Homepage uses port 3100 to avoid conflict with AdGuard (port 3000)
- Config files support environment variable substitution via {{HOMEPAGE_VAR_*}}
- Docker socket mounted read-only for security
- Other service integrations will be added in subsequent tickets
