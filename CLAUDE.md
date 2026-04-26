# CLAUDE.md

## Project Overview

Self-hosted Docker Compose infrastructure stack: home automation, workflow automation, VPN, DNS/ad-blocking, and monitoring. Domain-based routing via Traefik reverse proxy with Let's Encrypt SSL.

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
| `make logs-<service>` | Logs for one service (n8n, homepage, bede, etc.) |
| `make update` | Pull latest images and restart |
| `make build` | Build all (includes custom services) |
| `make validate` | Validate docker-compose config |
| `make test-domain-access` | Test HTTPS access to all services |
| `make clean` | Remove containers/volumes (preserves ./data/) |
| `make purge` | **DESTRUCTIVE** — removes everything including ./data/ |

**Bede AI services** (also included in main targets):
`make bede-start` / `bede-stop` / `bede-restart` / `bede-pull` / `bede-status`

**SSL**: `make ssl-setup` / `ssl-renew-test`

**WireGuard**: `make wireguard-status` / `wireguard-peers` / `wireguard-test` / `wireguard-routing`
Add peers: `sudo ./scripts/wireguard/wireguard-add-peer.sh <name>`

## Architecture

### Compose File Organization
- `docker-compose.yml` — Core services (AdGuard, n8n)
- `docker-compose.network.yml` — Network & security (Traefik, Fail2ban)
- `docker-compose.monitoring.yml` — Monitoring (Prometheus, Grafana, Alertmanager, exporters)
- `docker-compose.dashboard.yml` — Dashboard (Homepage, Homepage API)
- `docker-compose.ai.yml` — AI services (Bede — prebuilt GHCR image from josephradford/bede)

The Makefile combines all five files by default.

### Domain Routing
1. **AdGuard Home** (port 53) resolves `*.DOMAIN` → `SERVER_IP`
2. **Traefik** (ports 80/443) routes by Host header to the correct container
3. Services register via Docker labels: `Host(\`<service>.${DOMAIN}\`)`

### SSL (certbot, not Traefik ACME)
Uses certbot with Gandi DNS plugin because Traefik v3.2's Lego library has a bug with Gandi API v5 (returns 403 on DNS-01 challenge despite valid credentials). Certbot generates wildcard certs for `*.DOMAIN`, copies them to `./data/traefik/certs/`, Traefik loads via file provider. Auto-renewal runs twice daily via snap timer with a post-hook that copies certs and restarts Traefik.

### WireGuard VPN
Runs as a **system service** (`wg-quick@wg0`), not Docker — stays up when Docker restarts. Split tunneling only routes home network and VPN subnet traffic. **Do not use `0.0.0.0/0` for AllowedIPs** unless full tunneling is explicitly required.

### Security Model (Defense in Depth)
1. **UFW firewall** — default deny, allow SSH/HTTP/HTTPS/WireGuard + local/VPN subnets
2. **Traefik middleware** — `admin-secure` chain: RFC1918 IP whitelist + security headers + rate limiting on all admin UIs; `webhook-secure` chain for public endpoints
3. **Fail2ban** — auto-bans on auth failures, scanner patterns, rate limit abuse (config in `config/fail2ban/`)
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

### Deploying Bede changes

Bede source lives in a separate repo (josephradford/bede). The deploy workflow is:

1. Make changes in the bede repo, create a PR, merge to main
2. **Wait for GitHub Actions to build and push the new GHCR image** — do not deploy until the build completes
3. On the server: `make bede-pull && make bede-restart`

## Testing Checklist

Before submitting: `make validate` passes, services start healthy, no log errors, domain access works, `.env.example` updated for new vars, no secrets committed.
