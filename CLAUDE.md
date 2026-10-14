# CLAUDE.md

## Project Overview

Self-hosted Docker Compose infrastructure stack: home automation, workflow automation, DNS/ad-blocking, and monitoring. Built around a UniFi Dream Router 7 (UDR7), which provides routing, DHCP and the WireGuard VPN. Domain-based routing via Traefik reverse proxy with Let's Encrypt SSL.

## Development Environment

**This stack runs on a dedicated home server, not the dev Mac.**

- Code is edited locally, committed, pushed, and deployed to the server via SSH/git pull
- `make start` / `docker compose up` on the Mac won't help troubleshoot production
- DNS routing, SSL certs, and service access only work on the server's network
- `make validate` works locally for syntax checks
- For production debugging: SSH into the server, then `make logs` / `make status`

## Make Targets

| Target | Purpose |
|--------|---------|
| `make setup` | First-time setup (SSL, DNS, passwords) |
| `make start` / `stop` / `restart` | Manage all services |
| `make status` | Service health check |
| `make logs` | Follow all service logs |
| `make logs-<service>` | Logs for one service (homepage, etc.) |
| `make update` | Pull latest images and restart |
| `make build` | Build all (includes custom services) |
| `make validate` | Validate docker-compose config |
| `make test-domain-access` | Test HTTPS access to all services |
| `make clean` | Remove containers/volumes (preserves ./data/) |
| `make purge` | **DESTRUCTIVE** — removes everything including ./data/ |

**Odd jobs**: `make logs-odd-jobs` / `jobs-test` (local unit tests) / `jobs-probe` (check live fixture sources, writes nothing)

**SSL**: `make ssl-setup` / `ssl-renew-test`

**Dynamic DNS**: `make ddns-setup` / `ddns-update` / `ddns-status` (keeps `vpn.DOMAIN` pointed at the public IP for the UDR7 VPN)

## Architecture

### Compose File Organization
- `docker-compose.yml` — Core services (AdGuard)
- `docker-compose.network.yml` — Network & security (Traefik, Fail2ban)
- `docker-compose.monitoring.yml` — Monitoring (Prometheus, Grafana, Alertmanager, node-exporter, cAdvisor, blackbox-exporter)
- `docker-compose.dashboard.yml` — Dashboard (Homepage, Homepage API)
- `docker-compose.location.yml` — Location services (owntracks-recorder)
- `docker-compose.photos.yml` — iCloud photo backup (icloudpd)
- `docker-compose.immich.yml` — Photo viewer (immich-server, immich-machine-learning, immich-postgres, immich-redis)
- `docker-compose.library.yml` — Ebook library (cwa)
- `docker-compose.kiosk.yml` — Kitchen kiosk (kiosk-api, kiosk-web; sources in `apps/kitchen-kiosk/`)
- `docker-compose.radmap.yml` — Radmap (offline NSW topo map PWA; prebuilt GHCR image, tiles in `./data/radmap/tiles`)
- `docker-compose.jobs.yml` — Odd jobs (odd-jobs: AI-free life-admin jobs: sports fixture calendars at jobs.${DOMAIN} and the daily RSS-to-EPUB reading digest into `data/cwa/ingest`; sources in `apps/odd-jobs/`)

The Makefile combines all of these files by default (see `COMPOSE` in the Makefile
for the authoritative list).

### Services Outside the Standard Pattern
- **Polled UIs** (kiosk, Immich) use the `admin-secure-no-ratelimit` middleware, since `admin-secure`'s rate limit returns 429s for constantly polling clients.
- **Odd jobs** is a Python service built locally (`make build`); tests via `make jobs-test`, live source check via `make jobs-probe`. Staleness is alerted by `OddJobsStale` in `monitoring/prometheus/alert_rules.yml`.

### Domain Routing
1. **AdGuard Home** (port 53) resolves `*.DOMAIN` → `SERVER_IP`
2. **Traefik** (ports 80/443) routes by Host header to the correct container
3. Services register via Docker labels: `Host(\`<service>.${DOMAIN}\`)`

### SSL (certbot, not Traefik ACME)
Uses certbot with Gandi DNS plugin because Traefik v3.2's Lego library has a bug with Gandi API v5 (returns 403 on DNS-01 challenge despite valid credentials). Certbot generates wildcard certs for `*.DOMAIN`, copies them to `./data/traefik/certs/`, Traefik loads via file provider. Auto-renewal runs twice daily via snap timer with a post-hook that copies certs and restarts Traefik.

### Router and VPN (UniFi Dream Router 7)
The UDR7 is the network's router, DHCP server and **WireGuard VPN endpoint**; WireGuard no longer runs on this server (the old `wg-quick@wg0` service and `scripts/wireguard/` were removed). Its DHCP DNS and the VPN's DNS point at `SERVER_IP`, so AdGuard Home on this server stays the LAN resolver (and resolves `*.DOMAIN`). VPN peers are managed in the UniFi Network app. The VPN subnet is `VPN_SUBNET` in `.env` (used by UFW). Keep split tunneling (home network + VPN subnet only); **do not route `0.0.0.0/0`** unless full tunneling is explicitly required. If this server is down, DNS (and so the internet) is down, but VPN access to the router survives.

### Security Model (Defense in Depth)
1. **UFW firewall** — default deny, allow SSH/HTTP/HTTPS + local/UDR7-VPN subnets (`scripts/system/setup-firewall.sh`)
2. **Traefik middleware** — `admin-secure` chain: RFC1918 IP whitelist + security headers + rate limiting on all admin UIs; `webhook-secure` chain for public endpoints
3. **Fail2ban** — two layers: system-level sshd jail (`scripts/system/setup-fail2ban.sh`, whitelists local/VPN subnets) + Docker-level for Traefik auth failures, scanner patterns, rate limit abuse (`config/fail2ban/`)
4. **Prometheus alerts** — monitors 401s, 404s, 429s, 5xx errors (rules in `monitoring/prometheus/alert_rules.yml`)

### Data Persistence
All in `./data/` using bind mounts. Backup: `tar -czf backup.tar.gz data/ .env`

## Key Patterns

### Traefik Labels for New Services
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.<service>.rule=Host(`<service>.${DOMAIN}`)"
  - "traefik.http.routers.<service>.entrypoints=websecure"
  - "traefik.http.routers.<service>.tls=true"
  - "traefik.http.services.<service>.loadbalancer.server.port=<internal-port>"
```

### Adding a New Service
1. Add to appropriate compose file with Traefik labels
2. Add env vars to `.env.example`
3. Add to Homepage dashboard (`config/homepage/services-template.yaml`) with `showStats: true`
4. Update `SERVICES.md`
5. Test: `make validate && make start && make test-domain-access`

### Environment Variables
See `.env.example` for the complete variable list with descriptions. Dollar signs in passwords must be escaped as `$$` for Docker Compose.

## Git Workflow

GitHub Flow: `main` is production. Feature branches (`feature/`, `fix/`, `docs/`). PRs with squash merge.

## Testing Checklist

Before submitting: `make validate` passes, services start healthy, no log errors, domain access works, `.env.example` updated for new vars, no secrets committed.
