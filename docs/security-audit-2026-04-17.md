# Security Audit — 2026-04-17

Audit of the home-server-stack repo, grouped by severity. File:line references point to state at the time of the audit.

## Critical

### 1. No `detect-secrets` safety net for `.env`
The live `.env` contains real credentials (Telegram bot token, Gandi PAT, service passwords, API keys). `.gitignore` blocks it today, but a bad `git add -A` or a misconfigured hook would leak everything.
- **Fix:** add `detect-secrets` (or equivalent) to `.pre-commit-config.yaml` as a defence-in-depth layer.

## High

### 2. `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`
`.env:48` — n8n workflow code can read every host env var, including all passwords and API tokens. If the n8n UI is ever accidentally exposed, an attacker with workflow-edit rights exfiltrates everything.
- **Fix:** set `N8N_BLOCK_ENV_ACCESS_IN_NODE=true` and pass secrets explicitly through n8n credentials.

### 3. cAdvisor runs `privileged: true`
`docker-compose.monitoring.yml:93-109` — privileged mode + mounts on `/`, `/sys`, `/var/run`. A cAdvisor compromise → host root. cAdvisor is also no longer actively maintained upstream.
- **Fix:** drop `privileged`, mount only the paths cAdvisor actually needs, or remove cAdvisor entirely (node-exporter + Prometheus cover most metrics).

### 4. Fail2ban with `network_mode: host` + `NET_ADMIN`/`NET_RAW`
`docker-compose.network.yml:274-292` — fail2ban parses Traefik logs with full iptables control. A log-injection exploit against a sloppy `failregex` can execute arbitrary actions.
- **Fix:** audit every filter in `config/fail2ban/filter.d/` for unsafe regex and shell metacharacters in actions. Consider running fail2ban in its own network namespace.

### 5. Docker socket mounted into homepage + homepage-api
`docker-compose.dashboard.yml:30,84` — even `:ro`, the Docker API exposes full cluster topology and enables reconnaissance. Combined with a Flask/Homepage RCE, this is a cluster-wide foothold.
- **Fix:** insert a `tecnativa/docker-socket-proxy` sidecar that exposes only the container/stats endpoints homepage actually needs.

## Medium

### 6. `:latest` image tags across production services
Prometheus, Grafana, Alertmanager, AdGuard, n8n, Homepage, Fail2ban all use `:latest`. `docker compose pull` can silently upgrade to breaking or regressed versions.
- **Fix:** pin versions and enable Renovate or Dependabot for controlled updates.

### 7. Prometheus + Alertmanager bound directly on `SERVER_IP`
`docker-compose.monitoring.yml:7,60` — `9090` and `9093` are published on the LAN IP, bypassing Traefik's admin-secure middleware for anyone on the local network or on a VPN client that reaches those ports.
- **Fix:** remove the `ports:` blocks, use `expose:`, and access only via `prometheus.${DOMAIN}` / `alerts.${DOMAIN}`.

### 8. Unrestricted CORS on homepage-api
`homepage-api/app.py:20` — `CORS(app)` allows every origin.
- **Fix:** `CORS(app, origins=[f"https://homepage.{DOMAIN}"], credentials=True)`.

### 9. No secret rotation policy
Gandi PAT, Telegram bot token, Transport NSW, TomTom, Google OAuth — all long-lived with no documented rotation cadence.
- **Fix:** document a rotation schedule (e.g. Gandi PAT every 6 months, bot token quarterly) and record the procedure.

### 10. TomTom geocoding has no input bounds
`homepage-api/app.py:388-408` — URL-encoded but not length-capped or region-restricted.
- **Fix:** cap input length, whitelist Australian bounding box, rate-limit per unique origin/destination pair.

## Low

### 11. No `read_only: true` on containers
A compromised service can drop persistence artefacts on its rootfs.
- **Fix:** add `read_only: true` + `tmpfs: ["/tmp", "/run"]` where state is runtime-only.

### 12. No resource limits
No `deploy.resources.limits` on any service — one runaway process can DoS the host.
- **Fix:** add `cpus` and `memory` limits/reservations per service.

### 13. No Docker log rotation
- **Fix:** set `log-driver: json-file` with `max-size: 10m, max-file: 3` in each service or daemon-wide.

### 14. Fail2ban filter rules not reviewed for ReDoS
Catastrophic backtracking in `failregex` could be weaponised via crafted log lines.
- **Fix:** run regex rules through a ReDoS linter, or restrict to known-good community rules.

## Positive observations

- Every Traefik router has explicit `admin-secure` or `dashboard-secure` middleware — no accidental exposures.
- IP whitelist (RFC1918 + VPN subnet) + rate limiting + HSTS preload on admin routes.
- Bede Telegram handlers all check `ALLOWED_USER_ID` before processing commands.
- data-ingest and data-mcp use parameterised SQLite queries throughout — no SQLi.
- Bede subprocess calls use list args, no `shell=True`.
- UFW default-deny incoming + WireGuard split tunnelling (no `0.0.0.0/0`).
- Traefik v3.6.2 (patched), not the old 3.2 line with the Gandi/Lego issues.

## Top 5 to fix first

1. Add `detect-secrets` pre-commit hook.
2. `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`.
3. Remove direct `SERVER_IP:9090` / `:9093` binds; route only through Traefik.
4. Pin all `:latest` images and enable Renovate/Dependabot.
5. Replace raw docker.sock mounts with a socket-proxy sidecar.
