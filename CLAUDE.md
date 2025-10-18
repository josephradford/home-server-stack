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
```

### Logs & Debugging
```bash
# View all service logs (follow mode)
make logs

# View specific service logs
make logs-n8n
make logs-wireguard

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

### Testing & Validation
```bash
# Test domain-based access for all services
make test-domain-access

# Manually test DNS resolution
dig @${SERVER_IP} n8n.${DOMAIN} +short

# Configure AdGuard DNS rewrites manually
make adguard-setup
```

### Cleanup
```bash
# Remove containers and volumes (preserves ./data/)
make clean

# Nuclear option: remove everything including ./data/ (DESTRUCTIVE)
make purge
```

### Running Tests
```bash
# Test WireGuard routing configuration
./scripts/test-wireguard-routing.sh

# Test domain access
./scripts/test-domain-access.sh
```

## Architecture & Key Concepts

### Multi-File Docker Compose
The stack uses **two compose files** that are always composed together:
- `docker-compose.yml` - Core services (AdGuard, n8n, WireGuard, Traefik)
- `docker-compose.monitoring.yml` - Monitoring stack (Grafana, Prometheus, Alertmanager, exporters)

The Makefile always combines both: `docker compose -f docker-compose.yml -f docker-compose.monitoring.yml`

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

### VPN-First Security Model
The security architecture prioritizes **VPN access as the primary boundary**:
- Only WireGuard port (51820/UDP) exposed to internet by default
- All services accessible only via VPN or LAN
- Optional: Selective public exposure (e.g., n8n webhooks only via reverse proxy with path filtering)
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

**Current Branch**: `feature/letsencrypt-ssl` (adding Let's Encrypt SSL support)

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

### VPN Management
- `scripts/test-wireguard-routing.sh` - Validates WireGuard routing configuration

- `scripts/wireguard-peer-management.sh` - Manages WireGuard VPN peer configurations

## Monitoring Stack

**Metrics Collection**:
- Prometheus scrapes metrics every 15s from node-exporter (system) and cAdvisor (containers)
- Grafana visualizes metrics with pre-configured dashboards
- Alertmanager handles alert routing and notifications

**Alert Configuration**:
- Rules defined in `monitoring/prometheus/alert_rules.yml`
- Alertmanager config in `monitoring/alertmanager/alertmanager.yml`
- Alerts routed to webhook (default: `http://127.0.0.1:5001/`)
- See `docs/ALERTS.md` for alert definitions and `docs/RUNBOOK.md` for response procedures

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

### WireGuard
- LinuxServer.io container with s6-overlay init system
- Requires `NET_ADMIN` and `SYS_MODULE` capabilities (cannot drop or use no-new-privileges)
- Peer DNS points to AdGuard: `PEERDNS=${SERVER_IP}`
- Split tunneling via `WIREGUARD_ALLOWEDIPS`

## Documentation Structure

Comprehensive docs in `docs/` directory:
- `SETUP.md` - Installation guide
- `CONFIGURATION.md` - Service configuration
- `OPERATIONS.md` - Day-to-day management, updates, backups
- `TROUBLESHOOTING.md` - Common issues and solutions
- `ARCHITECTURE.md` - Detailed system design
- `MONITORING_DEPLOYMENT.md` - Monitoring setup guide
- `ALERTS.md` - Alert definitions
- `RUNBOOK.md` - Alert response procedures
- `REMOTE_ACCESS.md` - VPN and port forwarding setup

Implementation roadmaps:
- `monitoring-tickets/README.md` - Monitoring implementation roadmap
- `security-tickets/README.md` - Security hardening roadmap (VPN-first strategy)

## When Making Changes

### Adding a New Service
1. Add service definition to appropriate compose file
2. Add Traefik labels for domain-based routing
3. Add environment variables to `.env.example` with descriptive comments
4. Update service list in `SERVICES.md`
5. Add monitoring if needed (Prometheus scrape target)
6. Update documentation (README.md, relevant docs/)
7. Test: `make validate && make start && make test-domain-access`

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
**Implementation (certbot + file provider)**:
- Certificates: `./data/traefik/certs/DOMAIN.crt` (644) and `DOMAIN.key` (600)
- Dynamic config: `./config/traefik/dynamic-certs.yml` must exist
- Check if file provider loaded: `docker compose logs traefik | grep "file.Provider"`
- Check if certs loaded: `docker compose logs traefik | grep "Adding certificate"`
- Verify certs in container: `docker exec traefik ls -la /certs/` and `docker exec traefik ls -la /etc/traefik/`
- After config changes, must recreate container: `docker compose stop traefik && docker compose rm -f traefik && docker compose up -d traefik`
- Browser caching: Browsers may cache old certificates - clear cache or use Cmd+Shift+R (Safari especially prone to this)

**Troubleshooting certbot**:
- View certificates: `sudo certbot certificates`
- Test renewal: `sudo certbot renew --dry-run`
- Check Gandi credentials: `sudo cat /etc/letsencrypt/gandi/gandi.ini` (should have `dns_gandi_token`)
- Renewal logs: `sudo tail -f /var/log/certbot-traefik-reload.log`
- Verify DNS propagation: `dig @1.1.1.1 ${DOMAIN} +short`

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