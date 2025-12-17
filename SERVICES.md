# Services

A comprehensive catalog of all services in this homelab stack - running, planned, and under consideration.

## Access Methods

All services are accessible via two methods:

1. **Domain-based (Recommended):** `https://servicename.${DOMAIN}`
2. **IP:port (Legacy):** `http://SERVER_IP:PORT`

---

## Running

Currently deployed and active services.

### Management Services

#### Traefik Dashboard
- **Purpose:** Reverse proxy management
- **Access:** https://traefik.${DOMAIN}
- **Authentication:** Basic auth (admin / configured password)
- **Features:**
  - View active routers
  - Monitor service health
  - Check SSL certificates
  - View access logs

### Core Services

#### AdGuard Home
- **Purpose:** Network-wide ad blocking and DNS server
- **Access:** https://adguard.${DOMAIN}
- **Legacy:** http://SERVER_IP:8888
- **Port:** 8888 (admin), 53 (DNS)
- **Authentication:** Set during initial setup

#### n8n
- **Purpose:** Workflow automation with AI
- **Access:** https://n8n.${DOMAIN}
- **Legacy:** https://SERVER_IP:5678
- **Port:** 5678
- **Authentication:** N8N_USER / N8N_PASSWORD from .env

#### Home Assistant
- **Purpose:** Location tracking and home automation
- **Access:** https://home.${DOMAIN}
- **Legacy:** http://SERVER_IP:8123
- **Port:** 8123
- **Authentication:** Set during initial setup
- **Features:**
  - Family location tracking via iOS/Android Companion App
  - iCloud device tracking (AirPods, iPads, etc.)
  - Home automation and location-based triggers
  - Integration with n8n workflows

#### Actual Budget
- **Purpose:** Self-hosted personal finance and budgeting
- **Access:** https://actual.${DOMAIN}
- **Port:** 5006 (internal)
- **Authentication:** No login required (VPN/local access only)
- **Features:**
  - Privacy-focused budgeting with local data storage
  - Bank sync support (SimpleFIN, GoCardless)
  - Mobile apps for iOS and Android
  - End-to-end encrypted sync
  - Zero-based budgeting methodology

#### Mealie
- **Purpose:** Self-hosted meal planner and recipe manager
- **Access:** https://mealie.${DOMAIN}
- **Port:** 9000 (internal)
- **Authentication:** changeme@example.com / MyPassword (change after first login)
- **Features:**
  - Recipe management with image support and tags
  - Meal planning calendar with drag-and-drop interface
  - Automatic shopping list generation from meal plans
  - Recipe import from URLs (supports 1000+ websites)
  - Cooking mode with step-by-step instructions
  - Mobile-responsive web interface
  - RESTful API for integrations
  - Multi-user support with permissions
  - Mobile apps for iOS and Android

### Monitoring Stack

#### Grafana
- **Purpose:** Metrics visualization and dashboards
- **Access:** https://grafana.${DOMAIN}
- **Legacy:** http://SERVER_IP:3001
- **Port:** 3001
- **Authentication:** admin / GRAFANA_PASSWORD

#### Prometheus
- **Purpose:** Metrics collection and alerting
- **Access:** https://prometheus.${DOMAIN}
- **Legacy:** http://SERVER_IP:9090
- **Port:** 9090
- **Authentication:** None (VPN-protected)

#### Alertmanager
- **Purpose:** Alert routing and management
- **Access:** https://alerts.${DOMAIN}
- **Legacy:** http://SERVER_IP:9093
- **Port:** 9093
- **Authentication:** None (VPN-protected)

#### Node Exporter
- **Purpose:** System metrics exporter
- **Port:** 9100 (internal only)

#### cAdvisor
- **Purpose:** Container metrics
- **Port:** 8080 (internal only)

---

## Quick Reference

| Service | Domain | Legacy |
|---------|--------|--------|
| Traefik | https://traefik.${DOMAIN} | N/A |
| AdGuard | https://adguard.${DOMAIN} | http://IP:8888 |
| n8n | https://n8n.${DOMAIN} | http://IP:5678 |
| Home Assistant | https://home.${DOMAIN} | http://IP:8123 |
| Actual Budget | https://actual.${DOMAIN} | N/A |
| Mealie | https://mealie.${DOMAIN} | N/A |
| Grafana | https://grafana.${DOMAIN} | http://IP:3001 |
| Prometheus | https://prometheus.${DOMAIN} | http://IP:9090 |
| Alertmanager | https://alerts.${DOMAIN} | http://IP:9093 |

---

## Planned

Services queued for implementation.

### Application Services
- [ ] **[Glance](https://github.com/glanceapp/glance)** - Personal dashboard that puts all your feeds in one place
- [ ] **[HortusFox](https://github.com/danielbrendel/hortusfox-web)** - Collaborative plant management system
- [ ] **[Habitica](https://github.com/HabitRPG/habitica)** - Gamified habit and task tracker
- [ ] **[Bookwyrm](https://github.com/bookwyrm-social/bookwyrm)** - Social reading and book tracking platform
- [ ] **[Kiwix](https://github.com/kiwix)** - Offline content reader with ZIM file support for Wikipedia and educational content
- [ ] **[Immich](https://github.com/immich-app/immich)** - High performance self-hosted photo and video management solution (Apple Photos alternative)
- [ ] **[Jellyfin](https://github.com/jellyfin/jellyfin)** - The Free Software Media System for movies, TV shows, and music
- [ ] **[Navidrome](https://github.com/navidrome/navidrome)** - Modern Music Server and Streamer compatible with Subsonic/Airsonic (alternative to Jellyfin for music)
- [ ] **[Sonarr](https://github.com/Sonarr/Sonarr)** - Smart PVR for newsgroup and bittorrent users (TV show automation)
- [ ] **[Radarr](https://github.com/Radarr/Radarr)** - Movie organizer/manager for usenet and torrent users

### Infrastructure & Security
- [ ] **[Ollama](https://github.com/ollama/ollama)** - Run large language models locally
- [ ] **[Watchtower](https://github.com/containrrr/watchtower)** - A process for automating Docker container base image updates
- [ ] **[Fail2ban](https://github.com/fail2ban/fail2ban)** - Daemon to ban hosts that cause multiple authentication errors
- [ ] **[SearXNG](https://github.com/searxng/searxng)** - Free internet metasearch engine which aggregates results from various search services
- [ ] **[CrowdSec](https://github.com/crowdsecurity/crowdsec)** - Open-source and participative security solution with crowdsourced protection against malicious IPs
- [ ] **[Nginx Proxy Manager](https://github.com/NginxProxyManager/nginx-proxy-manager)** - Docker container for managing Nginx proxy hosts with a simple, powerful interface (alternative to Traefik)
- [ ] **[Duplicati](https://github.com/duplicati/duplicati)** - Store securely encrypted backups in the cloud

## Won't Do

Services that are popular, I have considered, but decided they don't fit my use case.

- **[Calibre-Web](https://github.com/janeczku/calibre-web)** - Web app for browsing, reading and downloading eBooks stored in a Calibre database
- **[Gitea](https://github.com/go-gitea/gitea)** - Git with a cup of tea! Painless self-hosted all-in-one software development service
- **[Authentik](https://github.com/goauthentik/authentik)** - The authentication glue you need (Identity Provider and SSO)

## Tried & Removed

Services that were tested but didn't make the cut.

- None yet

---

**Legend:**
- Services in "Running" are currently deployed and active
- Services in "Planned" are queued for future implementation
- Move services to "Won't Do" if they don't fit the use case after consideration
- Document in "Tried & Removed" with reasons for future reference
