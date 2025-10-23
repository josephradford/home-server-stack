#!/bin/bash
set -e

# Configure Homepage Dashboard
# This script creates the Homepage config files with our customized versions
# Only runs if config files don't already exist (preserves existing configuration)

echo "🏠 Configuring Homepage Dashboard"
echo "=================================="

# Load environment variables
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

source .env

# Ensure config directory exists
CONFIG_DIR="data/homepage/config"
mkdir -p "$CONFIG_DIR"

# Check if config files already exist
if [ -f "$CONFIG_DIR/services.yaml" ] && [ -f "$CONFIG_DIR/settings.yaml" ]; then
    echo "ℹ️  Homepage configuration files already exist"
    echo ""
    echo "⚠️  WARNING: Overwriting will replace your existing configuration!"
    echo ""
    echo "Would you like to overwrite them? (y/N)"
    read -r response

    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        echo ""
        echo "✓ Keeping existing configuration"
        echo ""
        exit 0
    fi

    echo ""
    echo "📝 Overwriting existing configuration files..."
    echo ""
else
    echo "📝 Creating Homepage configuration files..."
    echo ""
fi

echo "📝 Writing services.yaml..."
cat > "$CONFIG_DIR/services.yaml" <<'EOF'
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

# Transport & Commute section - to be populated in Ticket 06
- Transport & Commute:
    # Will be added in Ticket 06

# Family & Location section - to be populated in Ticket 03
- Family & Location:
    # Will be added in Ticket 03

# Calendar & Tasks section
- Calendar & Tasks:
    - BOM Weather:
        icon: mdi-weather-partly-cloudy
        href: http://www.bom.gov.au/
        description: Australian weather forecast
        widget:
          type: customapi
          url: http://homepage-api:5000/api/bom/weather
          refreshInterval: 300000  # 5 minutes
          mappings:
            - field: observations.temp
              label: Temperature
              suffix: "°C"
            - field: observations.temp_feels_like
              label: Feels Like
              suffix: "°C"
            - field: observations.humidity
              label: Humidity
              suffix: "%"
            - field: forecast_daily.0.short_text
              label: Today
EOF

echo "📝 Writing settings.yaml..."
cat > "$CONFIG_DIR/settings.yaml" <<'EOF'
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
EOF

echo "📝 Writing widgets.yaml..."
cat > "$CONFIG_DIR/widgets.yaml" <<'EOF'
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
EOF

echo "📝 Writing docker.yaml..."
cat > "$CONFIG_DIR/docker.yaml" <<'EOF'
---
# Docker socket configuration for container monitoring
my-docker:
  socket: /var/run/docker.sock
EOF

echo "📝 Writing bookmarks.yaml..."
cat > "$CONFIG_DIR/bookmarks.yaml" <<'EOF'
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
EOF

echo "✅ Homepage configuration complete!"
echo ""
echo "Configuration files written to $CONFIG_DIR/"
echo "  - services.yaml (with BOM weather widget)"
echo "  - settings.yaml"
echo "  - widgets.yaml"
echo "  - docker.yaml"
echo "  - bookmarks.yaml"
