# Home Server Stack

A complete self-hosted infrastructure for home automation, AI, and network services using Docker Compose.

**Built around a UniFi Dream Router 7 (UDR7).** The UDR7 is the network's router, Wi-Fi, DHCP server and WireGuard VPN endpoint. This server is a plain LAN host behind it: it runs DNS (AdGuard Home), reverse proxy and apps, and nothing on it terminates the VPN. See [Network setup (UDR7)](#-network-setup-udr7).

## 🚀 Services

**Core:** [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) (DNS/ad-blocking), [Traefik](https://github.com/traefik/traefik) (reverse proxy), OwnTracks Recorder (location)

**Monitoring:** [Grafana](https://github.com/grafana/grafana), [Prometheus](https://github.com/prometheus/prometheus), [Alertmanager](https://github.com/prometheus/alertmanager), Node Exporter, cAdvisor, blackbox-exporter, [unpoller](https://github.com/unpoller/unpoller) (UDR7 metrics)

**Dashboard:** [Homepage](https://github.com/gethomepage/homepage) + custom API backend

**Backup:** [icloudpd](https://github.com/icloud-photos-downloader/icloud_photos_downloader) container mirroring iCloud photo libraries to an external drive

**Library:** [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated) ebook library with Kobo sync, paired with an `odd-jobs` digest job that turns RSS feeds into a daily EPUB

**Photos:** [Immich](https://github.com/immich-app/immich) viewer over the icloudpd backups (read-only)

**Network:** [NetAlertX](https://github.com/jokob-sk/NetAlertX) LAN device scanner, blackbox-exporter router/ISP/DNS probes

**Home:** Kitchen Kiosk (iPad photo/calendar/radio display), [Radmap](https://github.com/josephradford/radmap) offline topo maps, Odd Jobs (AI-free life-admin jobs; v1 publishes cricket fixture calendars)

See [SERVICES.md](SERVICES.md) for the complete catalog including planned services.

## 📋 Fresh Install (New Server)

Follow these steps in order on a fresh Ubuntu Server 24.04 LTS machine.

### Step 1 — Clone the repo

```bash
git clone <your-repo-url>
cd home-server-stack
```

### Step 2 — Install Docker (official repository)

Ubuntu sometimes ships with snap Docker, which lacks the `docker` group needed for rootless access. This script replaces it with Docker CE from Docker's official apt repository.

```bash
./scripts/system/install-docker-official.sh
```

### Step 3 — Add user to docker group

Allows running `docker` and `make` targets without `sudo`.

```bash
./scripts/system/setup-user-permissions.sh
```

After this script completes, **log out and log back in** for the group change to take effect. Then update `PGID` in your `.env` to match the `docker` group GID printed by the install script.

### Step 4 — Configure environment

```bash
cp .env.example .env
nano .env
```

At minimum, set:
- `SERVER_IP` — the server's local network IP (e.g. `192.168.1.100`)
- `DOMAIN` — your registered domain name
- `TIMEZONE` — your timezone (e.g. `Australia/Sydney`)
- `LETSENCRYPT_EMAIL` and `GANDIV5_PERSONAL_ACCESS_TOKEN` — for SSL certificates
- All `*_PASSWORD` variables — change every default

### Step 5 — Configure firewall (UFW)

Requires the `.env` file (reads `VPN_SUBNET`, the VPN subnet configured on the UDR7).

```bash
./scripts/system/setup-firewall.sh
```

This sets default-deny incoming, rate-limits SSH, and opens ports for HTTP and HTTPS and allows the local network and UDR7 VPN subnet.

### Step 6 — First-time setup (SSL + services)

```bash
make setup
```

This runs SSL certificate generation (Let's Encrypt wildcard via certbot + Gandi DNS), configures AdGuard DNS rewrites, and starts all services.

### Step 7 — Set up the VPN on the UDR7

The VPN is WireGuard running on the UDR7, so remote access works even when this server is down. Follow [Network setup (UDR7)](#-network-setup-udr7) below. If your public IP is dynamic, run `make ddns-setup` so `vpn.DOMAIN` follows it (see [docs/ddns.md](docs/ddns.md)).

### Step 8 — Verify everything is running

```bash
make status          # All services healthy
make test-domain-access  # Domain routing works
```

---

**Using the Makefile (day-to-day):**
- `make help` - Show all available commands
- `make setup` - First time setup (all services + monitoring)
- `make update` - Update all services to latest versions
- `make start` - Start all services
- `make stop` - Stop all services
- `make logs` - View logs from all services
- See `make help` for complete list of commands

**Access Services:**

All services are accessible via domain names on your local network:

- **Traefik Dashboard:** `https://traefik.${DOMAIN}`
- **AdGuard Home:** `https://adguard.${DOMAIN}` (DNS admin)
- **Grafana:** `https://grafana.${DOMAIN}` (Monitoring)
- **Prometheus:** `https://prometheus.${DOMAIN}` (Metrics)
- **Alertmanager:** `https://alerts.${DOMAIN}` (Alerts)
- **Homepage:** `https://homepage.${DOMAIN}` (Dashboard)
- **OwnTracks Recorder:** `https://owntracks.${DOMAIN}` (Location history API)
- **NetAlertX:** `https://netalertx.${DOMAIN}` (LAN device scanner)
- **Immich:** `https://immich.${DOMAIN}` (Photos)
- **Books:** `https://books.${DOMAIN}` (Calibre-Web-Automated)
- **Kitchen Kiosk:** `https://kiosk.${DOMAIN}`
- **Radmap:** `https://radmap.${DOMAIN}` (Offline maps)
- **Odd Jobs:** `https://jobs.${DOMAIN}` (calendar subscriptions at `/<name>.ics`)

**Note:** Services are accessible via domain names thanks to Traefik reverse proxy and AdGuard Home DNS. Your devices must use AdGuard Home as their DNS server (configured automatically if DHCP points to the server).

**Direct Access (Emergency/Operational):** Some services expose direct ports for specific use cases:
- AdGuard Home: `http://SERVER_IP:8888` (emergency access if Traefik fails)
- Prometheus: `http://SERVER_IP:9090` (metrics scraping)
- Alertmanager: `http://SERVER_IP:9093` (alert routing)

These are not intended for regular use - domain-based access via Traefik is recommended. See [SERVICES.md](SERVICES.md) for complete list.

## 📚 Documentation

**Primary documentation:**
- **[CLAUDE.md](CLAUDE.md)** - Complete operational guide (setup, configuration, operations, troubleshooting)
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and visual diagrams
- **[SERVICES.md](SERVICES.md)** - Service catalog with access details

All operational knowledge is consolidated in CLAUDE.md which covers:
- Initial setup and configuration
- Service management and operations
- SSL certificate setup with Let's Encrypt
- Troubleshooting common issues
- Architecture and design decisions

## 🌐 Network setup (UDR7)

The UDR7 handles routing, DHCP and the VPN. Configure it in the UniFi Network app:

1. **LAN**: keep the server on a fixed address (DHCP reservation for `SERVER_IP`). The stack assumes `192.168.1.0/24`.
2. **DNS**: set the LAN's DHCP DNS server to `SERVER_IP` so every device uses AdGuard Home. This is what resolves `*.DOMAIN` to the server and does the ad blocking. AdGuard stays on this server; the UDR7's built-in blocking is coarser.
3. **VPN**: create a WireGuard VPN server (Settings > VPN) and add one peer per device. Set the VPN **DNS server to `SERVER_IP`**, otherwise remote clients can't resolve `*.DOMAIN`. Keep split tunnelling (home network and VPN subnet only; never `0.0.0.0/0` unless you really want full tunnelling).
4. **Subnet**: set `VPN_SUBNET` in `.env` to the VPN subnet you chose, then re-run `./scripts/system/setup-firewall.sh` so UFW allows it.
5. **Endpoint**: clients connect to `vpn.DOMAIN` (kept current by `make ddns-setup`) or your static public IP. No port forwarding to this server is needed, because the UDR7 is the VPN endpoint.

VPN clients reach this server as routed LAN traffic from the VPN subnet. Traefik's `admin-secure` allowlist already covers all private ranges.

## 🔐 Security

This project implements **multi-layered defense-in-depth security** with four protection layers:

### Security Layers

**🔥 Layer 1: Network Firewall (UFW)**
- Default deny incoming, SSH rate-limited
- Nothing is exposed to the internet; remote access goes through the UDR7's VPN
- HTTP/HTTPS (80/443) are open to the local network and VPN clients, who have full access

**🛡️ Layer 2: Traefik Middleware**
- **IP Whitelisting**: Admin interfaces only accessible from local network/VPN
- **Security Headers**: HSTS, XSS protection, frame deny
- **Rate Limiting**: 10 req/min for admin, 100 req/min for webhooks

**🚫 Layer 3: Fail2ban**
- Auto-bans IPs after repeated auth failures (3 → 1h ban)
- Detects scanning activity (10 x 404 → 24h ban)
- Monitors webhook abuse (20 x rate limit → 10m ban)

**📊 Layer 4: Prometheus Security Monitoring**
- Real-time alerts for auth failures, scanning, DDoS attempts
- Tracks rate limit enforcement and server errors
- Monitors fail2ban and Traefik availability

### Access Model

- **Admin Interfaces** (Grafana, etc.): VPN or local network only
- **Future Webhooks**: Public access with rate limiting (not yet configured)
- **VPN Primary Boundary**: the UDR7's WireGuard VPN for all remote admin access

## 📊 Dashboard & Automation

This stack includes a comprehensive dashboard with integrations:

- **Homepage**: Unified dashboard for all services
- **Backend API**: Custom integrations for BOM weather, Transport NSW, traffic

### Deploy Dashboard Services

```bash
docker compose -f docker-compose.dashboard.yml up -d
```

See **[CLAUDE.md](CLAUDE.md)** for detailed dashboard setup instructions.

### Dashboard Features

- 🌤️ Australian BOM weather for North Parramatta
- 📅 Google Calendar integration
- 🚊 Real-time Transport NSW departures
- 🚗 Traffic conditions for configurable routes
- 🌐 Network health (router/ISP latency, devices on the network) and external outage status
- 🐳 Docker container monitoring

## 🤝 Contributing

Contributions are welcome! Submit bug reports and feature requests via [GitHub Issues](https://github.com/josephradford/home-server-stack/issues). Follow the branching strategy documented in [CLAUDE.md](CLAUDE.md) (GitHub Flow — feature branches, squash merge to main).

## 📊 System Requirements

**Minimum:**
- 8 GB RAM (16 GB recommended)
- 500 GB storage (1 TB recommended)
- Linux-based OS (tested on Ubuntu Server 24.04 LTS)
- Docker and Docker Compose installed


## 📄 License

This project is open source. Individual services maintain their own licenses:
- AdGuard Home: GPL-3.0
- Traefik: MIT
- Grafana: AGPL-3.0
- Prometheus: Apache-2.0

## 💬 Support

- **Documentation**: See [CLAUDE.md](CLAUDE.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
- **Issues**: [GitHub Issues](https://github.com/josephradford/home-server-stack/issues)
- **Service-specific docs**:
  - [AdGuard Home](https://adguard.com/kb/)
  - [Traefik](https://doc.traefik.io/traefik/)

---

**Project Status:** Active Development
**Latest Update:** 2026-10-07
