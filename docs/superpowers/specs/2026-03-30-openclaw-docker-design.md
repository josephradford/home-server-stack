# OpenClaw Docker Integration — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## Overview

Re-introduce OpenClaw AI assistant to the home server stack using the official pre-built Docker image. Previous attempts failed due to: Homebrew in Docker (slow, heavy), interactive onboarding wizard (incompatible with automation), and complex PATH issues. The official image and JSON5 config-with-env-var-interpolation eliminate all three problems.

**Goals:**
- Single `make start` brings OpenClaw up with no manual steps
- Config fully driven from `.env` — no interactive wizard
- Consistent with rest of stack: Traefik, admin-secure middleware, domain-based access
- Telegram channel configured out of the box

**Out of scope:**
- Google integrations (GOG/Calendar/Gmail) — add later via `OPENCLAW_EXTENSIONS`
- iMessage — requires macOS, not supported on Linux server
- WhatsApp — previously painful, skipped

---

## Architecture

OpenClaw runs as a single `openclaw-gateway` container on the existing `homeserver` Docker network. Traefik routes `https://openclaw.${DOMAIN}` to it with the `admin-secure` middleware (IP whitelist + security headers + rate limiting). No separate onboarding/CLI service is needed.

```
User (VPN/LAN) → Traefik → openclaw-gateway:18789
                              ↑
                   data/openclaw/openclaw.json  (rendered config, gitignored)
                   data/openclaw/workspace/     (agent workspace, gitignored)
```

Config is generated from a committed template (`config/openclaw/openclaw.json.template`) by a setup script (`scripts/openclaw/configure-openclaw.sh`) that uses `envsubst` to substitute `.env` values into the template at setup time, producing a rendered `data/openclaw/openclaw.json`. This is a new pattern in the stack — not the same as `configure-homepage.sh`, which copies template files without substitution (Homepage resolves `{{HOMEPAGE_VAR_*}}` at runtime instead).

---

## Components

### `docker-compose.openclaw.yml`

Single service using the official pre-built image. No custom Dockerfile.

- **Image:** `${OPENCLAW_IMAGE:-ghcr.io/openclaw/openclaw:latest}`
- **Restart:** `unless-stopped`
- **Network:** `homeserver` (external, shared with all other services)
- **Volumes:**
  - `./data/openclaw:/home/node/.openclaw` — all OpenClaw data including rendered config, workspace, and runtime state (gitignored)
- **Ports:** Not published directly — Traefik proxies via the Docker network
- **Traefik labels:** `admin-secure` middleware, `Host(\`openclaw.${DOMAIN}\`)`
- **Health check:** `GET /healthz` (liveness) and `GET /readyz` (readiness), 30s interval, 40s start period
  - **Note:** Verify these endpoint paths against the official image before implementation. If unavailable, fall back to a TCP port check or omit.
- **COMPOSE_CORE:** Excluded — Traefik SSL and AdGuard DNS operations should not restart OpenClaw

### `config/openclaw/openclaw.json.template`

Committed config template with `${VAR_NAME}` placeholders. Rendered into `data/openclaw/openclaw.json` at setup time by `scripts/openclaw/configure-openclaw.sh`. Contains no secrets.

```json5
{
  gateway: {
    bind: "0.0.0.0:18789",
    token: "${OPENCLAW_GATEWAY_TOKEN}",
    // trustedProxies covers the Docker bridge CIDR (172.16.0.0/12 = full RFC1918 172.x block).
    // This is intentionally broad: admin-secure middleware already enforces IP allowlisting
    // at the Traefik layer, so only LAN/VPN clients ever reach OpenClaw. The /12 avoids
    // hardcoding a specific Docker network subnet that may vary across installations.
    // To tighten: replace with output of:
    //   docker network inspect homeserver --format '{{(index .IPAM.Config 0).Subnet}}'
    trustedProxies: ["172.16.0.0/12"],
  },
  agents: {
    defaults: {
      model: {
        primary: "anthropic/claude-sonnet-4-6",
      },
      env: {
        ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}",
      },
    },
  },
  channels: {
    telegram: {
      token: "${TELEGRAM_BOT_TOKEN}",
      // Only allow messages from explicitly paired users
      dmPolicy: "pairing",
    },
  },
}
```

### `scripts/openclaw/configure-openclaw.sh`

Renders the config template into `data/openclaw/openclaw.json` using `envsubst`.

1. Creates `data/openclaw/` if it doesn't exist
2. Loads `.env`
3. Runs `envsubst` on `config/openclaw/openclaw.json.template` → `data/openclaw/openclaw.json`
4. Sets permissions (640)

Unlike `configure-homepage.sh` (which copies files unchanged), this script performs variable substitution at setup time so the container receives real values baked in.

### `.env` additions

Four new variables (add to `.env.example` with documentation):

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude model access |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `OPENCLAW_GATEWAY_TOKEN` | Secret token for Control UI access (generate with `openssl rand -hex 32`) |
| `OPENCLAW_IMAGE` | Optional: pin to a specific image tag (default: `ghcr.io/openclaw/openclaw:latest`) |

### Makefile changes

- **`COMPOSE`** — updated to include `docker-compose.openclaw.yml` (all five files)
- **`COMPOSE_CORE`** — unchanged (three files, no OpenClaw)
- **`.PHONY`** — add `logs-openclaw`
- **`make setup`** — insert OpenClaw config generation as **Step 4/9**, shifting existing steps 4-8 to 5-9:
  - Step 1: Traefik password
  - Step 2: SSL cert storage
  - Step 3: Homepage dashboard config
  - **Step 4: OpenClaw config** ← new
  - Step 5: Pull images (was 4)
  - Step 6: Build custom services (was 5)
  - Step 7: Start services (was 6)
  - Step 8: Fix permissions (was 7)
  - Step 9: AdGuard DNS (was 8)
  - Update all step echo strings from `x/8` to `x/9`
  - Add `https://openclaw.$$DOMAIN` to the completion message service URL list
- **`make logs-openclaw`** — new target, tails `openclaw-gateway` logs
- **`make help`** — add `logs-openclaw` under Logs & Debugging

### `scripts/testing/test-domain-access.sh`

Add `test_domain "openclaw.${DOMAIN}" "OpenClaw AI Assistant"` to the `test_domain` call block (lines 194-201).

Do **not** add `openclaw-gateway` to the `services=` pre-flight array (line 154). That array enforces hard exits if a container is not running — since `docker-compose.openclaw.yml` is an optional fifth file, treating OpenClaw as a required pre-flight dependency would break `make test-domain-access` for any user who hasn't deployed it. The `test_domain` call alone is sufficient: it will attempt the HTTP check and report pass/fail without a hard exit.

---

## Data Persistence & Git Hygiene

| Path | Committed? | Purpose |
|---|---|---|
| `config/openclaw/openclaw.json.template` | Yes | Config template, no secrets |
| `data/openclaw/openclaw.json` | No (gitignored) | Rendered config with substituted values |
| `data/openclaw/workspace/` | No (gitignored) | Agent workspace, session data, cron runs |

`./data/` is already gitignored at the top level. No additional gitignore entries needed.

---

## Security

- **Access:** `admin-secure` middleware — IP whitelist (RFC1918 + VPN), HSTS, rate limiting
- **Auth:** `OPENCLAW_GATEWAY_TOKEN` required for all Control UI and API access
- **trustedProxies:** `172.16.0.0/12` (full RFC1918 172.x block, see comment in template above)
- **Telegram dmPolicy:** `pairing` — only explicitly paired users can interact with the bot
- **Port:** Not published directly; only reachable via Traefik on the internal Docker network

---

## Compose File Organisation

| File | Contents |
|---|---|
| `docker-compose.yml` | Core services (AdGuard, n8n) |
| `docker-compose.network.yml` | Traefik, Fail2ban |
| `docker-compose.monitoring.yml` | Prometheus, Grafana, Alertmanager, exporters |
| `docker-compose.dashboard.yml` | Homepage, Homepage API |
| `docker-compose.openclaw.yml` | OpenClaw gateway |

---

## Setup Flow (first time)

1. Add `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `OPENCLAW_GATEWAY_TOKEN` to `.env`
2. `make setup` — renders config template and starts all services including OpenClaw
3. Visit `https://openclaw.${DOMAIN}` — log in with `OPENCLAW_GATEWAY_TOKEN`
4. Pair Telegram bot: send `/start` to the bot in Telegram

No custom Dockerfile, no Homebrew, no interactive wizard, no `tty: true`.

---

## Not Included

- Custom Dockerfile — official image is sufficient
- Separate `openclaw-cli` onboarding service — config template eliminates the need
- Google/GOG integrations — add later via `OPENCLAW_EXTENSIONS` in `.env`
- iMessage — requires macOS
