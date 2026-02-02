# Services

A comprehensive catalog of all services in this homelab stack - running, planned, and under consideration.

## Access Methods

All services are accessible via domain-based routing through Traefik:

1. **Domain-based (Primary):** `https://servicename.${DOMAIN}`

Some services also expose direct ports for emergency/operational access:

2. **Direct Access (Emergency/Operational):** `http://SERVER_IP:PORT`
   - Used when Traefik is unavailable or for direct metrics scraping
   - Not intended for regular use

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
- **Direct Access:** http://SERVER_IP:8888 (emergency access if Traefik fails)
- **Port:** 8888 (admin), 53 (DNS)
- **Authentication:** Set during initial setup

#### n8n
- **Purpose:** Workflow automation with AI
- **Access:** https://n8n.${DOMAIN}
- **Legacy:** https://SERVER_IP:5678
- **Port:** 5678
- **Authentication:** N8N_USER / N8N_PASSWORD from .env

#### OpenClaw AI Assistant (Native Installation)
- **Purpose:** AI assistant accessible via messaging apps (Telegram, WhatsApp, Discord)
- **Installation:** Native systemd service (NOT Docker) - installed directly on Ubuntu server
- **Access:** http://${SERVER_IP}:18789 (web UI, local network only)
- **Setup:** `make openclaw-install` (run on server)
- **Authentication:** None (local network access only, no Traefik routing)
- **Features:**
  - Conversational AI powered by Anthropic Claude
  - Multi-platform messaging support (Telegram, WhatsApp, Discord)
  - Sandboxed code execution for programming tasks
  - Long-polling mode (default) - no webhook or public URL needed
  - Persistent chat history and session data (stored on server: ~/.openclaw/)
  - Runs as systemd user service (auto-starts on boot)
- **Management:**
  - Check status: `make openclaw-status` (run on server)
  - View logs: `make openclaw-logs` (run on server)
  - Manual commands: `openclaw gateway status`, `openclaw health`

### Monitoring Stack

#### Grafana
- **Purpose:** Metrics visualization and dashboards
- **Access:** https://grafana.${DOMAIN}
- **Port:** 3000 (internal)
- **Authentication:** admin / GRAFANA_PASSWORD

#### Prometheus
- **Purpose:** Metrics collection and alerting
- **Access:** https://prometheus.${DOMAIN}
- **Direct Access:** http://SERVER_IP:9090 (for metrics scraping)
- **Port:** 9090
- **Authentication:** None (VPN-protected)

#### Alertmanager
- **Purpose:** Alert routing and management
- **Access:** https://alerts.${DOMAIN}
- **Direct Access:** http://SERVER_IP:9093 (for alert routing)
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
| OpenClaw (Native) | N/A | http://IP:18789 |
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
