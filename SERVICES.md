# Services

A comprehensive catalog of all services in this homelab stack - running, planned, and under consideration.

## Running

Currently deployed and active services.

- **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome)** - Network-wide ads & trackers blocking DNS server
- **[n8n](https://github.com/n8n-io/n8n)** - Fair-code workflow automation platform with native AI capabilities
- **[Ollama](https://github.com/ollama/ollama)** - Get up and running with local large language models (deepseek-coder:6.7b, llama3.2:3b)
- **[WireGuard](https://github.com/wireguard)** - Fast, modern, secure VPN tunnel for remote access
- **[Habitica](https://github.com/HabitRPG/habitica)** - Gamified habit and task tracker (RPG-style productivity)
- **[Bookwyrm](https://github.com/bookwyrm-social/bookwyrm)** - Social reading and reviewing, decentralized with ActivityPub
- **[Grafana](https://github.com/grafana/grafana)** - The open and composable observability and data visualization platform (optional monitoring stack)
- **[Prometheus](https://github.com/prometheus/prometheus)** - The Prometheus monitoring system and time series database (optional monitoring stack)
- **[Alertmanager](https://github.com/prometheus/alertmanager)** - Prometheus Alertmanager for handling alerts (optional monitoring stack)
- **[Node Exporter](https://github.com/prometheus/node_exporter)** - Exporter for machine metrics (optional monitoring stack)
- **[cAdvisor](https://github.com/google/cadvisor)** - Analyzes resource usage and performance characteristics of running containers (optional monitoring stack)

## Planned

Services queued for implementation.

- [ ] **[Kiwix](https://github.com/kiwix)** - Offline content reader with ZIM file support for Wikipedia and educational content
- [ ] **[Immich](https://github.com/immich-app/immich)** - High performance self-hosted photo and video management solution (Apple Photos alternative)
- [ ] **[Tandoor Recipes](https://github.com/TandoorRecipes/recipes)** - Application for managing recipes, planning meals, and building shopping lists
- [ ] **[Actual Budget](https://github.com/actualbudget/actual)** - A local-first personal finance app
- [ ] **[Watchtower](https://github.com/containrrr/watchtower)** - A process for automating Docker container base image updates
- [ ] **[Fail2ban](https://github.com/fail2ban/fail2ban)** - Daemon to ban hosts that cause multiple authentication errors
- [ ] **[SearXNG](https://github.com/searxng/searxng)** - Free internet metasearch engine which aggregates results from various search services
- [ ] **[CrowdSec](https://github.com/crowdsecurity/crowdsec)** - Open-source and participative security solution with crowdsourced protection against malicious IPs
- [ ] **[HortusFox](https://github.com/danielbrendel/hortusfox-web)** - Self-hosted collaborative plant management system for plant enthusiasts
- [ ] **[Glance](https://github.com/glanceapp/glance)** - A self-hosted dashboard that puts all your feeds in one place
- [ ] **[Jellyfin](https://github.com/jellyfin/jellyfin)** - The Free Software Media System for movies, TV shows, and music
- [ ] **[Navidrome](https://github.com/navidrome/navidrome)** - Modern Music Server and Streamer compatible with Subsonic/Airsonic (alternative to Jellyfin for music)
- [ ] **[Sonarr](https://github.com/Sonarr/Sonarr)** - Smart PVR for newsgroup and bittorrent users (TV show automation)
- [ ] **[Radarr](https://github.com/Radarr/Radarr)** - Movie organizer/manager for usenet and torrent users
- [ ] **[Nginx Proxy Manager](https://github.com/NginxProxyManager/nginx-proxy-manager)** - Docker container for managing Nginx proxy hosts with a simple, powerful interface
- [ ] **[Traefik](https://github.com/traefik/traefik)** - The Cloud Native Application Proxy (alternative to Nginx Proxy Manager)
- [ ] **[Duplicati](https://github.com/duplicati/duplicati)** - Store securely encrypted backups in the cloud

## Won't Do

Services that are popular, I have considered, but decided they don't fit my use case.

- **[Calibre-Web](https://github.com/janeczku/calibre-web)** - Web app for browsing, reading and downloading eBooks stored in a Calibre database
- **[Home Assistant](https://github.com/home-assistant/core)** - Open source home automation that puts local control and privacy first
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
