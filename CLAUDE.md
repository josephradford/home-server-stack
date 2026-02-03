# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a self-hosted infrastructure stack running on Docker Compose, providing home automation, workflow automation, VPN access, DNS/ad-blocking, and comprehensive monitoring. Services are accessed via domain-based routing through Traefik reverse proxy with Let's Encrypt SSL certificates.

## Development Environment Context

**IMPORTANT**: This stack is designed to run on a dedicated home server (e.g., Ubuntu Server at 192.168.1.100), not on the development machine where code is edited.

**Typical workflow**:
- Code changes are made on the development machine (e.g., MacBook)
- Changes are committed and pushed to git
- Changes are deployed to the actual home server via SSH or git pull
- Troubleshooting is done by SSHing into the home server and checking logs there

**What this means for development**:
- Running `make start` or `docker compose up` on the development machine **will not help with troubleshooting** production issues
- DNS-based routing requires AdGuard Home to be the network DNS server, which only works on the home server's network
- SSL certificates are obtained for the registered domain and won't work locally without proper DNS setup
- When debugging issues, use SSH to connect to the home server and run commands there:
  ```bash
  ssh user@192.168.1.100
  cd /path/to/home-server-stack
  make logs  # View actual logs from the running services
  make status  # Check service health
  ```
- Configuration validation (`make validate`) can be done locally before pushing changes
- For local testing of docker-compose syntax, you can run validation but not the actual services

## Common Development Commands

### Environment Setup
```bash
# One-time: Install Docker from official repository (if using snap Docker)
# Check: which docker (if shows /snap/bin/docker, run the installer)
./scripts/install-docker-official.sh

# One-time: Add user to docker group (enables docker commands without sudo)
./scripts/setup-user-permissions.sh

# Copy environment template and configure
cp .env.example .env
# Edit .env - set SERVER_IP, DOMAIN, passwords, GANDIV5_PERSONAL_ACCESS_TOKEN

# Validate configuration
make validate
```

### Service Management
```bash
# First-time setup (includes SSL cert setup and AdGuard DNS configuration)
make setup

# Start all services (core + monitoring)
make start

# Stop all services
make stop

# Restart services
make restart

# View service status
make status
```

### Updates & Maintenance
```bash
# Pull latest images and restart services
make update

# Pull images without restarting
make pull

# Build custom services from source (homepage-api)
make build-custom

# Build all services (includes custom services)
make build
```

### Logs & Debugging
```bash
# View all service logs (follow mode)
make logs

# View specific service logs
make logs-n8n
make logs-homepage

# View logs directly (useful for other services)
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml logs -f [service-name]
```

### SSL Certificate Management
```bash
# Complete Let's Encrypt SSL setup (certbot + auto-renewal)
make ssl-setup

# Individual SSL operations
make ssl-copy-certs           # Copy certs from /etc/letsencrypt to Traefik
make ssl-configure-traefik    # Configure Traefik file provider
make ssl-setup-renewal        # Setup automatic renewal
make ssl-renew-test          # Test renewal (dry run)

# Manual certificate operations (advanced)
sudo certbot certificates                    # View certificate info
sudo certbot renew --dry-run                # Test renewal
sudo certbot renew --force-renewal          # Force renewal
sudo tail -f /var/log/certbot-traefik-reload.log  # View renewal logs
```

### WireGuard VPN Management
```bash
# Install WireGuard package (one-time)
make wireguard-install

# Create server config and start service
make wireguard-setup

# Check WireGuard status
make wireguard-status

# Add VPN peers (clients) one at a time
sudo ./scripts/wireguard-add-peer.sh mydevice
sudo ./scripts/wireguard-add-peer.sh phone

# View detailed status
sudo wg show
sudo systemctl status wg-quick@wg0
```

### Service Configuration
```bash
# Configure AdGuard DNS rewrites for domain-based access
make adguard-setup

# Generate Traefik dashboard password from .env
make traefik-password
```

### OpenClaw AI Assistant (Native Installation)
```bash
# NOTE: Run these commands ON the server, not from your dev machine
# SSH to server first: ssh user@SERVER_IP

# Install OpenClaw natively (interactive)
make openclaw-install

# Check OpenClaw service status
make openclaw-status

# View OpenClaw gateway logs (live stream)
make openclaw-logs

# Manual operations
openclaw gateway status        # Check gateway status
openclaw health               # Health check
openclaw onboard              # Re-run onboarding
journalctl --user -u openclaw-gateway -f  # View systemd logs
```

### Dashboard Management
```bash
# Setup Homepage dashboard (first time)
make dashboard-setup

# Start/stop/restart Homepage dashboard
make dashboard-start
make dashboard-stop
make dashboard-restart

# View Homepage dashboard logs
make dashboard-logs

# Show Homepage dashboard status
make dashboard-status
```

### Testing & Validation
```bash
# Test domain-based access for all services
make test-domain-access

# Manually test DNS resolution
dig @${SERVER_IP} n8n.${DOMAIN} +short

# Validate docker-compose configuration
make validate

# Check environment file exists
make env-check
```

### Cleanup
```bash
# Remove containers and volumes (preserves ./data/)
make clean

# Nuclear option: remove everything including ./data/ (DESTRUCTIVE)
make purge
```

## Architecture & Key Concepts

### Multi-File Docker Compose
The stack uses **four compose files** organized by logical function:
- `docker-compose.yml` - Core services (AdGuard, n8n) - user-facing services that "do stuff"
- `docker-compose.network.yml` - Network & Security (Traefik, Fail2ban) - infrastructure layer
- `docker-compose.monitoring.yml` - Monitoring stack (Prometheus, Grafana, Alertmanager, exporters)
- `docker-compose.dashboard.yml` - Dashboard (Homepage, Homepage API)

**Note on WireGuard VPN**: WireGuard is installed as a **system service** (not Docker) to ensure VPN access remains available when Docker services are restarted or stopped. See "WireGuard VPN Management" section above.

The Makefile combines all files by default: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml`

This organization provides:
- **Clear separation of concerns** - Easy to understand what each file contains
- **Logical grouping** - Services grouped by function (core, network, monitoring, dashboard)
- **Modular deployment** - Can deploy subsets if needed (e.g., core + network without monitoring)
- **Homepage dashboard alignment** - Dashboard sections mirror compose file organization

### Domain-Based Routing Architecture
Services are accessed via **subdomain.DOMAIN** instead of IP:port combinations:

1. **AdGuard Home** (DNS server on port 53) resolves `*.DOMAIN` to `SERVER_IP`
2. **Traefik** (reverse proxy on ports 80/443) routes requests based on Host header
3. Services are discovered automatically via Docker labels: `traefik.http.routers.<service>.rule=Host(\`<service>.${DOMAIN}\`)`

Example flow: `https://n8n.example.com` → DNS resolves to SERVER_IP → Traefik routes to n8n container → HTTPS response

### SSL Certificates with Let's Encrypt (via certbot)
**Implementation**: Uses **certbot with Gandi DNS plugin** for Let's Encrypt wildcard certificates.

**Why certbot instead of Traefik's built-in ACME?**
- Traefik v3.2's Lego library (v4.21.0) has compatibility issues with Gandi API v5
- Manual API tests with Gandi succeed, but Lego consistently returns 403 Forbidden during DNS-01 challenge
- Root cause: Bug or incompatibility between Lego's Gandi provider and Gandi API v5
- Solution: Use certbot with `certbot-dns-gandi` plugin which works reliably with same credentials
- See `scripts/setup-certbot-gandi.sh` for detailed implementation

**How it works**:
1. **certbot** generates wildcard certificate for `*.DOMAIN` and `DOMAIN` via DNS-01 challenge
2. Certificates stored in `/etc/letsencrypt/live/DOMAIN/` (system location)
3. Copied to `./data/traefik/certs/` for Traefik access via file provider
4. Traefik configured with file provider to load certificates from `./config/traefik/dynamic-certs.yml`
5. Post-renewal hook automatically copies renewed certs and restarts Traefik

**Setup Commands**:
```bash
# Complete SSL setup (all steps)
make ssl-setup

# Individual steps
make ssl-copy-certs            # Copy certs from /etc/letsencrypt to Traefik
make ssl-configure-traefik     # Configure file provider
make ssl-setup-renewal         # Setup auto-renewal hook
make ssl-renew-test           # Test renewal (dry run)
```

**Auto-Renewal**:
- certbot runs twice daily via snap timer
- Certificates renewed 30 days before expiry (Let's Encrypt = 90 day validity)
- Post-renewal hook: `/etc/letsencrypt/renewal-hooks/deploy/traefik-reload.sh`
- Hook copies new certs to Traefik and runs `docker compose restart traefik`
- Logs: `/var/log/certbot-traefik-reload.log`

**Required Environment Variables**:
- `DOMAIN` - Registered domain name hosted on Gandi
- `ACME_EMAIL` - Email for Let's Encrypt notifications
- `GANDIV5_PERSONAL_ACCESS_TOKEN` - Gandi API token with "Manage domain name technical configurations" permission

**File Locations**:
- Certificates (source): `/etc/letsencrypt/live/DOMAIN/fullchain.pem`, `privkey.pem`
- Certificates (Traefik): `./data/traefik/certs/DOMAIN.crt`, `DOMAIN.key`
- Traefik dynamic config: `./config/traefik/dynamic-certs.yml`
- Renewal hook: `/etc/letsencrypt/renewal-hooks/deploy/traefik-reload.sh`
- Gandi credentials: `/etc/letsencrypt/gandi/gandi.ini` (chmod 600)

### Security Architecture

The stack implements **multi-layered defense-in-depth** security:

#### Layer 1: Network Firewall (UFW)
- Default deny incoming, allow outgoing
- SSH rate-limited (prevents brute force)
- WireGuard VPN (UDP 51820) - primary remote access
- HTTP/HTTPS (80/443) for Traefik reverse proxy
- Full access for local network (192.168.1.0/24) and VPN clients (10.13.13.0/24)
- Setup: `./scripts/setup-firewall.sh`

#### Layer 2: Traefik Middleware Security
**admin-secure middleware chain** (applied to all admin interfaces):
- IP whitelisting: Only RFC1918 (192.168.x.x, 10.x.x.x, 172.16.x.x) allowed
- Security headers: HSTS, XSS protection, frame deny, content-type nosniff
- Rate limiting: 10 requests/min (burst 5)
- Services: n8n, AdGuard, Grafana, Prometheus, Alertmanager, Traefik dashboard

**webhook-secure middleware chain** (ready for future public webhooks):
- Security headers (same as above)
- Generous rate limiting: 100 requests/min (burst 50)
- No IP restrictions (public access)

Middleware definitions in `docker-compose.yml` Traefik service labels.

#### Layer 3: Fail2ban Automated Defense
- Monitors Traefik access logs for malicious patterns
- **traefik-auth jail**: 3 x 401 errors → 1 hour ban
- **traefik-webhook jail**: 20 x rate limit hits → 10 minute ban
- **traefik-scanner jail**: 10 x 404 errors → 24 hour ban
- Ignores local/VPN networks from bans
- Config: `config/fail2ban/`

#### Layer 4: Prometheus Security Monitoring
- High webhook rate detection (>1 req/sec)
- Authentication failure monitoring (401 errors)
- Scanning activity detection (404 errors)
- Rate limit enforcement tracking (429 errors)
- Server error monitoring (5xx errors)
- Traefik and fail2ban availability monitoring
- Alerts: `monitoring/prometheus/alert_rules.yml` security-alerts group

#### VPN-First Access Model
- Primary remote access: WireGuard VPN only
- Admin interfaces: VPN or local network only (enforced by middleware)
- Future public webhooks: Separate router with webhook-secure middleware
- See `security-tickets/README.md` for complete security roadmap

### Data Persistence
All persistent data is stored in `./data/` using **bind mounts** (not Docker volumes):
- `./data/adguard/` - DNS configuration and logs
- `./data/n8n/` - Workflow database and files
- `./data/wireguard/` - VPN configs and peer keys
- `./data/traefik/` - SSL certificates and logs
- `./data/grafana/`, `./data/prometheus/`, etc. - Monitoring data

Backup strategy: `tar -czf backup.tar.gz data/ .env`

### WireGuard Split Tunneling
**Critical**: WireGuard is configured for **split tunneling** by default:
- `WIREGUARD_ALLOWEDIPS=192.168.1.0/24,10.13.13.0/24` routes only home network traffic
- **DO NOT** use `0.0.0.0/0` unless full tunneling is explicitly required
- This prevents routing all internet traffic through the VPN

## Important Environment Variables

Required variables in `.env`:
- `SERVER_IP` - Server's local network IP (e.g., 192.168.1.100)
- `DOMAIN` - Registered domain name (e.g., example.com) for Let's Encrypt
- `TIMEZONE` - System timezone (e.g., America/New_York)
- `GANDIV5_PERSONAL_ACCESS_TOKEN` - Gandi API token for DNS-01 challenge
- `ACME_EMAIL` - Email for Let's Encrypt certificate notifications
- `N8N_PASSWORD`, `ADGUARD_PASSWORD`, `GRAFANA_PASSWORD` - Service credentials
- `WIREGUARD_PORT`, `WIREGUARD_SUBNET`, `WIREGUARD_ALLOWEDIPS` - VPN configuration

**Dashboard & Integration Variables:**
- `TRANSPORT_NSW_API_KEY` - Transport NSW OpenData API key for real-time departures
- `TRANSPORT_STOP_*` - Transit stop IDs and display names for dashboard widgets
- `TOMTOM_API_KEY` - TomTom Traffic API key for traffic conditions
- `TRAFFIC_ROUTE_*` - Traffic route configurations with origin/destination and schedules
- `BOM_LOCATION` - Australian suburb name for Bureau of Meteorology weather
- `GOOGLE_CALENDAR_ICAL_URL` - Google Calendar iCal URL for calendar widget

See `.env.example` for complete variable list with descriptions and defaults.

**Additional Environment Variables** (see `.env.example` for full documentation):
- **Monitoring & Alerts:** `WEBHOOK_URL`, `ALERT_EMAIL_*` - AlertManager notification configuration
- **n8n Performance:** `DB_SQLITE_POOL_SIZE`, `N8N_RUNNERS_*`, `EXECUTIONS_TIMEOUT*` - Performance tuning
- **OpenClaw AI:** `ANTHROPIC_API_KEY` - AI assistant API key (required for native installation)
- **Dashboard:** `PUID`, `PGID`, `HOMEPAGE_ALLOWED_HOSTS` - Homepage permissions and access control
- **Service Credentials:** Various `*_USERNAME` and `*_PASSWORD` pairs for service authentication
- **WireGuard Advanced:** `WIREGUARD_SERVERURL` - Public IP for external VPN connections

**Password Escaping**: Dollar signs in passwords must be escaped as `$$` for Docker Compose (e.g., `P@$$word123` → `P@$$$$word123`)

## Docker Compose Labels Pattern

Services use Traefik labels for automatic routing:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.<service>.rule=Host(`<service>.${DOMAIN}`)"
  - "traefik.http.routers.<service>.entrypoints=websecure"
  - "traefik.http.routers.<service>.tls=true"
  - "traefik.http.routers.<service>.tls.certresolver=letsencrypt"
  - "traefik.http.services.<service>.loadbalancer.server.port=<internal-port>"
```

For wildcard certificate (only on dashboard router):
```yaml
- "traefik.http.routers.dashboard.tls.domains[0].main=${DOMAIN}"
- "traefik.http.routers.dashboard.tls.domains[0].sans=*.${DOMAIN}"
```

## Git Workflow

**Branching Strategy** (GitHub Flow):
- `main` - production-ready code
- Feature branches - `feature/description`, `fix/description`, `docs/description`
- All changes via pull requests with reviews

**Merge Strategy**:
- Squash and merge for feature branches (default)
- Create merge commit for releases

## Scripts Overview

### DNS & Domain Configuration
- `scripts/setup-adguard-dns.sh` - Configures AdGuard DNS rewrites for `*.DOMAIN` → `SERVER_IP`
  - Generates bcrypt password hash using htpasswd
  - Creates/updates `AdGuardHome.yaml` with DNS rewrites
  - Requires: `SERVER_IP`, `DOMAIN`, `ADGUARD_PASSWORD` in `.env`

- `scripts/test-domain-access.sh` - Tests HTTPS access to all services via domains

### Service Configuration
- `scripts/configure-homepage.sh` - Generates Homepage dashboard configuration files
  - Creates `services.yaml`, `widgets.yaml`, `docker.yaml` from templates
  - Substitutes environment variables in configuration
  - Called during `make setup` and `make dashboard-setup`

- `scripts/setup-traefik-password.sh` - Generates Traefik dashboard password hash
  - Reads `TRAEFIK_PASSWORD` from `.env`
  - Creates htpasswd-format hash for basic authentication
  - Sets `TRAEFIK_DASHBOARD_USERS` environment variable
  - Called during `make setup` and `make traefik-password`

### SSL Certificate Management (certbot)
- `scripts/setup-certbot-gandi.sh` - Installs certbot and generates Let's Encrypt wildcard certificate
  - Installs certbot via snap and certbot-dns-gandi via pip3
  - Handles Ubuntu 24.04 externally-managed Python environment (--break-system-packages)
  - Creates Gandi API credentials file at `/etc/letsencrypt/gandi/gandi.ini`
  - Generates wildcard cert for `*.DOMAIN` and `DOMAIN` using DNS-01 challenge
  - Requires: `DOMAIN`, `ACME_EMAIL`, `GANDIV5_PERSONAL_ACCESS_TOKEN` in `.env`

- `scripts/copy-certs-to-traefik.sh` - Copies certificates from Let's Encrypt to Traefik
  - Copies `/etc/letsencrypt/live/DOMAIN/fullchain.pem` → `./data/traefik/certs/DOMAIN.crt`
  - Copies `/etc/letsencrypt/live/DOMAIN/privkey.pem` → `./data/traefik/certs/DOMAIN.key`
  - Sets proper ownership and permissions (644 for cert, 600 for key)

- `scripts/configure-traefik-file-provider.sh` - Configures Traefik to use file provider
  - Creates `./config/traefik/dynamic-certs.yml` with certificate paths
  - Configures Traefik to load certificates from file instead of ACME
  - Must restart Traefik after running (use `make ssl-configure-traefik`)

- `scripts/setup-cert-renewal.sh` - Sets up automatic certificate renewal
  - Creates post-renewal hook: `/etc/letsencrypt/renewal-hooks/deploy/traefik-reload.sh`
  - Hook automatically copies renewed certs and restarts Traefik container
  - Creates log file: `/var/log/certbot-traefik-reload.log`
  - Tests renewal with dry run

### VPN Management (System Service)
- `scripts/install-wireguard.sh` - Installs WireGuard as system service (one-time setup)
- `scripts/setup-wireguard-server.sh` - Creates WireGuard server configuration
- `scripts/wireguard-add-peer.sh` - Adds VPN peers (clients) and generates client configs
- `scripts/setup-wireguard-routing.sh` - Configures WireGuard routing and forwarding
  - Sets up IP forwarding and NAT rules
  - Configures routing for split tunneling
  - Called during WireGuard server setup

- `scripts/test-wireguard-routing.sh` - Tests WireGuard routing configuration
  - Verifies IP forwarding is enabled
  - Checks NAT rules are configured
  - Tests connectivity through VPN

- `scripts/wireguard-peer-management.sh` - Advanced peer management utilities
  - List all configured peers
  - View peer statistics and connection status
  - Remove or modify existing peers

### Firewall & Security
- `scripts/setup-firewall.sh` - Configures UFW firewall rules
  - Sets up default deny incoming, allow outgoing
  - Allows SSH (rate-limited), HTTP/HTTPS, WireGuard
  - Permits full access from local network and VPN subnet
  - Called during initial server setup

### System Setup
- `scripts/install-docker-official.sh` - Installs Docker from official repository
  - Removes snap-based Docker installation
  - Adds Docker's official apt repository
  - Installs Docker Engine with proper dependencies
  - One-time setup for Ubuntu systems

- `scripts/setup-user-permissions.sh` - Adds user to docker group
  - Enables running docker commands without sudo
  - Creates docker group if it doesn't exist
  - Adds current user to docker group
  - Requires logout/login to take effect

## Monitoring Stack

**Metrics Collection**:
- Prometheus scrapes metrics every 15s from node-exporter (system) and cAdvisor (containers)
- Grafana visualizes metrics with pre-configured dashboards
- Alertmanager handles alert routing and notifications

**Alert Configuration**:
- Rules defined in `monitoring/prometheus/alert_rules.yml`
- Alertmanager config in `monitoring/alertmanager/alertmanager.yml`
- Alerts routed to webhook (default: `http://127.0.0.1:5001/`)

**Accessing Monitoring**:
- Grafana: `https://grafana.${DOMAIN}`
- Prometheus: `https://prometheus.${DOMAIN}` (also direct: `http://${SERVER_IP}:9090`)
- Alertmanager: `https://alerts.${DOMAIN}` (also direct: `http://${SERVER_IP}:9093`)

## Service-Specific Notes

### n8n
- Workflow automation platform with SQLite database
- Configured with Basic Auth: `N8N_USER` / `N8N_PASSWORD`
- Webhook URL: `https://n8n.${DOMAIN}/webhook/*`
- Environment variables include timeout settings and future compatibility flags
- Init container ensures proper permissions (`n8n-init` service)

### AdGuard Home
- Dual access: Domain-based (`https://adguard.${DOMAIN}`) and direct IP (`http://${SERVER_IP}:8888`)
- Configuration auto-generated by `setup-adguard-dns.sh` script
- Requires bcrypt password hash (generated via htpasswd)
- DNS rewrites configured as: `'*.${DOMAIN}' → ${SERVER_IP}`

### Traefik
- HTTP to HTTPS redirect configured on web entrypoint
- Dashboard accessible at `https://traefik.${DOMAIN}` with basic auth
- Debug logging enabled: `--log.level=DEBUG`
- Health check via ping endpoint
- **Certificate Management**: Uses file provider to load certbot-generated certificates
  - File provider watches `/etc/traefik/` directory (mapped to `./config/traefik/`)
  - Dynamic config: `./config/traefik/dynamic-certs.yml`
  - Certificates loaded from `/certs/` (mapped to `./data/traefik/certs/`)

### WireGuard (System Service)
- **System-level service** (not Docker) for VPN access
- Ensures VPN remains available when Docker services are restarted
- Configuration: `/etc/wireguard/wg0.conf`
- Peer configs: `./data/wireguard/peers/`
- Split tunneling configured to route only home network and VPN subnet traffic
- Auto-start enabled via systemd: `wg-quick@wg0`
- Status check: `sudo wg show` or `make wireguard-status`

### Homepage API (Custom Backend)
- **Purpose:** Custom Flask backend providing integrations for Homepage dashboard
- **Container:** `homepage-api` (built from `./homepage-api/`)
- **Internal port:** 5000
- **Domain access:** `https://homepage-api.${DOMAIN}`
- **Security:** admin-secure middleware (IP whitelist + rate limiting)
- **Features:**
  - BOM (Bureau of Meteorology) weather data for Australian locations
  - Transport NSW real-time departures API integration
  - TomTom traffic conditions with schedule-based filtering
  - WireGuard VPN system service monitoring (status, connected peers)
  - Docker daemon system service monitoring (status, container count, disk usage)
  - Health check endpoint at `/api/health`
- **Configuration:**
  - `BOM_LOCATION` - Australian suburb name for weather data
  - `TRANSPORT_NSW_API_KEY` - Transport NSW API key
  - `TRANSPORT_STOP_*` - Transit stop IDs and display names for dashboard widgets
  - `TOMTOM_API_KEY` - TomTom API key for traffic data
  - `TRAFFIC_ROUTE_*` - Multiple traffic routes with origin/destination/schedule
  - `GOOGLE_CALENDAR_ICAL_URL` - Google Calendar iCal URL for calendar widget
- **Why custom backend?**
  - Homepage widget framework limited for complex API integrations
  - Enables schedule-based filtering (e.g., show traffic only during commute hours)
  - Centralizes API key management and rate limiting
  - Provides caching layer to reduce external API calls
  - Monitors system services (WireGuard, Docker) that aren't visible as containers
- **Documentation:** See `homepage-api/README.md` for development and API endpoints

### Homepage Dashboard
- **Purpose:** Unified dashboard with system monitoring, service widgets, and custom integrations
- **Image:** `ghcr.io/gethomepage/homepage:latest`
- **Container:** `homepage`
- **Internal port:** 3000
- **Domain access:** `https://homepage.${DOMAIN}`
- **Security:** admin-secure-no-ratelimit middleware (IP whitelist without rate limiting)
- **Configuration:**
  - Service definitions: `./data/homepage/config/services.yaml` (from template `./config/homepage/services-template.yaml`)
  - Docker integration: mounts `/var/run/docker.sock` for container stats
  - Widget APIs: Integrates with AdGuard, Grafana, Transport NSW, BOM, TomTom
  - Environment templating: Uses `HOMEPAGE_VAR_*` env vars in configs
- **Data persistence:** `./data/homepage/config/`
- **Features:**
  - System resource monitoring (CPU, RAM, network) for all containers
  - Service health status and uptime
  - Application-specific widgets (AdGuard stats, Grafana dashboards)
  - Custom integrations via Homepage API backend
  - Calendar integration (Google Calendar via iCal)
- **Widget Architecture:**
  - **Container stats** (showStats: true) - System resources from Docker
  - **Application widgets** - App-specific metrics via APIs
  - Both are complementary: container stats = infrastructure, widgets = application metrics
- **Configuration:** See `config/homepage/services-template.yaml` for widget configuration

### OpenClaw AI Assistant (Native Installation)
- AI assistant accessible via messaging apps (Telegram, WhatsApp, Discord)
- Provides intelligent conversational interface with sandboxed code execution
- **Installation:** Native system service (NOT Docker) - runs directly on Ubuntu server
- Web UI access: `http://${SERVER_IP}:18789`
- Configuration: `~/.openclaw/` on server (not in repo)
- **Architecture:**
  - `openclaw-gateway` - systemd user service that connects messaging apps to AI
  - Runs on port 18789 (web UI) and 8787 (optional Telegram webhook)
  - Long-polling mode (default) requires no webhook or public URL
  - Sandbox execution - Isolated processes for running code tasks
- **Setup:**
  - Run on server (SSH to server first): `make openclaw-install`
  - Installation steps:
    1. Checks Node.js 22+ is installed
    2. Runs official OpenClaw installer: `curl -fsSL https://openclaw.ai/install.sh | bash`
    3. Runs onboarding wizard with `--install-daemon` flag
    4. Configures Telegram bot (requires Bot Token from @BotFather)
    5. Configures Anthropic API key (provided during onboarding)
    6. Starts gateway as systemd user service
  - Configuration via interactive onboarding wizard (run once during installation)
- **Configuration:**
  - Requires: `ANTHROPIC_API_KEY` in `.env` for Claude AI models
  - Recommended model: `claude-sonnet-4-5`
  - Configuration stored on server: `~/.openclaw/openclaw.json`
  - Channel sessions in `~/.openclaw/credentials/`
  - Telegram uses **long-polling** (default) - no webhook or reverse proxy needed
- **API Costs:**
  - Pay-per-use Anthropic API (no subscription)
  - Typical conversation: $0.05-0.50 per interaction
  - Monitor usage at console.anthropic.com
- **Security:**
  - Runs as native systemd user service (isolated from Docker)
  - API keys stored in server home directory (never commit to git)
  - Sandboxed code execution isolated from host
  - No Docker socket access required
  - Web UI accessible only from local network (port 18789 not exposed publicly)
  - Monitor for prompt injection risks
- **Management:**
  - Check status: `make openclaw-status` (run on server)
  - View logs: `make openclaw-logs` (run on server)
  - Health check: `openclaw health` (run on server)
  - Runs automatically on boot via systemd

## Documentation Structure

Comprehensive docs in `docs/` directory:
- `ARCHITECTURE.md` - Detailed system design and visual diagrams
- `archive/SETUP.md` - Installation guide
- `archive/CONFIGURATION.md` - Service configuration
- `archive/OPERATIONS.md` - Day-to-day management, updates, backups
- `archive/TROUBLESHOOTING.md` - Common issues and solutions
- `archive/MONITORING_DEPLOYMENT.md` - Monitoring setup guide
- `archive/ALERTS.md` - Alert definitions and response procedures
- `archive/REMOTE_ACCESS.md` - VPN and port forwarding setup
- `archive/BACKEND_API.md` - Homepage API backend documentation
- `archive/DASHBOARD_SETUP.md` - Homepage dashboard setup guide

Implementation roadmaps:
- `tickets/monitoring-tickets/README.md` - Monitoring implementation roadmap
- `tickets/security-tickets/README.md` - Security hardening roadmap (VPN-first strategy)

## When Making Changes

### Adding a New Service
1. Add service definition to appropriate compose file
2. Add Traefik labels for domain-based routing
3. Add environment variables to `.env.example` with descriptive comments
4. Update service list in `SERVICES.md`
5. Add monitoring if needed (Prometheus scrape target)
6. **IMPORTANT: Add to Homepage dashboard** (`config/homepage/services-template.yaml`):
   - Include container stats for resource monitoring:
     ```yaml
     - Service Name:
         icon: service-icon.png
         href: https://service.{{HOMEPAGE_VAR_DOMAIN}}
         description: Service description
         container: container-name  # Must match container_name in docker-compose
         server: my-docker          # References docker.yaml
         showStats: true            # Enables CPU, memory, network stats
     ```
   - If service has an API widget, include both widget AND container stats
   - Container stats show system resources (CPU, RAM, network)
   - Widgets show application metrics (queries, users, etc.)
   - Both are complementary, not redundant
7. Update documentation (README.md, relevant docs/)
8. Test: `make validate && make start && make test-domain-access`

### Modifying Environment Variables
1. Update `.env.example` with new/changed variables and comments
2. Update documentation mentioning those variables
3. Ensure backwards compatibility or document breaking changes
4. If adding secrets, ensure pre-commit hooks catch them (`.pre-commit-config.yaml`)

### Modifying Docker Compose
1. Always run `make validate` before committing
2. Test service starts correctly: `make start && make status`
3. Check logs for errors: `make logs`
4. Verify service accessibility via domain

### Modifying Scripts
1. Test script locally first
2. Ensure proper error handling (`set -e`)
3. Add helpful output with colors (see `setup-adguard-dns.sh` for example)
4. Update Makefile if script should be called via make target

## Common Issues

### SSL Certificate Issues

**Quick diagnostics:**
```bash
# Check certificates exist
ls -la ./data/traefik/certs/

# Verify Traefik loaded certs
docker compose logs traefik | grep -i certificate

# View Let's Encrypt certificate status
sudo certbot certificates

# Check renewal hook logs
sudo tail -20 /var/log/certbot-traefik-reload.log
```

**Common fixes:**
- Browser caching old cert: Clear cache or Cmd+Shift+R (Safari especially prone)
- File provider not loaded: Check `./config/traefik/dynamic-certs.yml` exists
- Permissions wrong: Cert should be 644, key should be 600
- After config changes: Must recreate container with `docker compose up -d --force-recreate traefik`

### DNS Resolution
- Ensure AdGuard is running: `docker compose ps adguard`
- Test DNS directly: `dig @${SERVER_IP} n8n.${DOMAIN} +short`
- Check AdGuard logs: `docker compose logs adguard`
- Verify DNS rewrites: `./scripts/setup-adguard-dns.sh`

### Service Not Accessible
1. Check service is running: `make status`
2. Check Traefik routing: `docker compose logs traefik | grep <service-name>`
3. Verify DNS resolves to SERVER_IP: `dig @${SERVER_IP} <service>.${DOMAIN}`
4. Test direct port access (if exposed): `curl http://${SERVER_IP}:<port>`

## Security Considerations

- **Never commit** `.env` files or secrets
- Pre-commit hooks scan for secrets (`.pre-commit-config.yaml`)
- All passwords must be changed from defaults in `.env.example`
- Docker images should be pinned versions (not `:latest` in production)
- VPN-first: Only WireGuard should be exposed to internet by default
- See `SECURITY.md` for security policy and vulnerability reporting
- See `security-tickets/README.md` for complete security roadmap

## Testing Checklist

Before submitting changes:
- [ ] `make validate` passes
- [ ] `make start` successfully starts all services
- [ ] `make status` shows all services as healthy
- [ ] `make logs` shows no errors
- [ ] `make test-domain-access` passes (if domain routing affected)
- [ ] Documentation updated for user-facing changes
- [ ] `.env.example` updated if new variables added
- [ ] No secrets committed (pre-commit hooks pass)