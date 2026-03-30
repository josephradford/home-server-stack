# OpenClaw Docker Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenClaw AI assistant to the home server stack using the official pre-built Docker image, fully configured via env-var-rendered template, behind Traefik with Telegram channel support.

**Architecture:** Single `openclaw-gateway` container on the existing `homeserver` network. Config is rendered at setup time via `envsubst` from a committed template into `data/openclaw/openclaw.json`. Traefik proxies `https://openclaw.${DOMAIN}` with `admin-secure` middleware — no interactive wizard, no Dockerfile.

**Tech Stack:** Docker Compose, Traefik reverse proxy, envsubst (GNU gettext), Bash

**Spec:** `docs/superpowers/specs/2026-03-30-openclaw-docker-design.md`

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `docker-compose.openclaw.yml` | OpenClaw service definition |
| Create | `config/openclaw/openclaw.json.template` | Config template with `${VAR}` placeholders |
| Create | `scripts/openclaw/configure-openclaw.sh` | Renders template → `data/openclaw/openclaw.json` |
| Modify | `Makefile` | COMPOSE var, setup steps 4/9, logs-openclaw target, help |
| Modify | `.env.example` | 4 new variables with documentation |
| Modify | `scripts/testing/test-domain-access.sh` | Add `test_domain` call for openclaw |
| Modify | `SERVICES.md` | Move OpenClaw from "Tried & Removed" to "Running" |
| Modify | `CLAUDE.md` | Add OpenClaw service documentation |

---

### Task 1: Create config template

**Files:**
- Create: `config/openclaw/openclaw.json.template`

- [ ] **Step 1: Create the config directory and template**

```bash
mkdir -p config/openclaw
```

Then create `config/openclaw/openclaw.json.template`:

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

- [ ] **Step 2: Verify template contains all four placeholder vars**

```bash
grep -o '\${[A-Z_]*}' config/openclaw/openclaw.json.template | sort
```

Expected output:
```
${ANTHROPIC_API_KEY}
${OPENCLAW_GATEWAY_TOKEN}
${TELEGRAM_BOT_TOKEN}
```

- [ ] **Step 3: Commit**

```bash
git add config/openclaw/openclaw.json.template
git commit -m "feat: add openclaw config template"
```

---

### Task 2: Create configure-openclaw.sh script

**Files:**
- Create: `scripts/openclaw/configure-openclaw.sh`

- [ ] **Step 1: Write a test script to verify the configure script works**

Create a temporary test: after writing the script, we'll manually verify it renders the template correctly (no automated test framework for shell scripts in this repo — verification is the "run and inspect" approach used elsewhere in the stack).

- [ ] **Step 2: Write the configure script**

Create `scripts/openclaw/configure-openclaw.sh`:

```bash
#!/bin/bash
set -e

# Configure OpenClaw AI Assistant
# Renders openclaw.json.template → data/openclaw/openclaw.json using envsubst
# Called during 'make setup' as Step 4/9

echo "🦅 Configuring OpenClaw AI Assistant"
echo "======================================"

# Load environment variables
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

source .env

TEMPLATE="config/openclaw/openclaw.json.template"
OUTPUT_DIR="data/openclaw"
OUTPUT="$OUTPUT_DIR/openclaw.json"

# Check template exists
if [ ! -f "$TEMPLATE" ]; then
    echo "❌ Error: Template not found: $TEMPLATE"
    exit 1
fi

# Check required variables
missing_vars=()
[ -z "$OPENCLAW_GATEWAY_TOKEN" ] && missing_vars+=("OPENCLAW_GATEWAY_TOKEN")
[ -z "$ANTHROPIC_API_KEY" ] && missing_vars+=("ANTHROPIC_API_KEY")
[ -z "$TELEGRAM_BOT_TOKEN" ] && missing_vars+=("TELEGRAM_BOT_TOKEN")

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Error: Missing required variables in .env:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Add these to your .env file and re-run setup."
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Render template
envsubst < "$TEMPLATE" > "$OUTPUT"

# Set permissions: readable by owner and group only (config contains secrets)
chmod 640 "$OUTPUT"

echo "✓ OpenClaw config rendered to $OUTPUT"
```

- [ ] **Step 3: Make executable**

```bash
chmod +x scripts/openclaw/configure-openclaw.sh
```

- [ ] **Step 4: Manually verify it renders correctly**

Add the three required variables temporarily to `.env`, then run:

```bash
# Add test values to .env if not present
echo 'OPENCLAW_GATEWAY_TOKEN=test-token-abc123' >> .env
echo 'ANTHROPIC_API_KEY=sk-test-key' >> .env
echo 'TELEGRAM_BOT_TOKEN=123456:test-bot-token' >> .env

./scripts/openclaw/configure-openclaw.sh

# Verify output contains rendered values (not placeholders)
cat data/openclaw/openclaw.json
```

Expected: The three `${VAR}` placeholders are replaced with the test values. No `${...}` remaining in output.

```bash
grep '\${' data/openclaw/openclaw.json && echo "FAIL: unreplaced placeholders" || echo "PASS: all vars rendered"
```

- [ ] **Step 5: Verify error handling for missing vars**

The script sources `.env` internally, so passing an empty env prefix won't work. Instead, create a minimal temp `.env` that's missing `OPENCLAW_GATEWAY_TOKEN`, run the script, then restore:

```bash
# Backup .env, create test version without OPENCLAW_GATEWAY_TOKEN
cp .env /tmp/.env.openclaw_backup
grep -v "^OPENCLAW_GATEWAY_TOKEN=" .env > /tmp/.env.test_missing
cp /tmp/.env.test_missing .env

# Verify the script catches the missing variable
./scripts/openclaw/configure-openclaw.sh 2>&1 | grep -q "Missing required variables" && echo "PASS: missing var detection works" || echo "FAIL"

# Restore .env
cp /tmp/.env.openclaw_backup .env
rm /tmp/.env.test_missing /tmp/.env.openclaw_backup
```

- [ ] **Step 6: Clean up test data and commit**

```bash
# Remove test data file (data/ is gitignored but clean up anyway)
rm -f data/openclaw/openclaw.json

# Remove test values from .env (edit .env manually to remove the three test lines added in Step 4)

# Verify no test credentials remain before committing
grep -E "sk-test-key|test-token-abc123|123456:test-bot-token" .env && echo "FAIL: test credentials still in .env" || echo "PASS: .env is clean"

git add scripts/openclaw/configure-openclaw.sh
git commit -m "feat: add openclaw configure script"
```

---

### Task 3: Create docker-compose.openclaw.yml

**Files:**
- Create: `docker-compose.openclaw.yml`

The official image is `ghcr.io/openclaw/openclaw:latest`. The container expects its config at `/home/node/.openclaw/openclaw.json`. We mount `./data/openclaw` to that path so the rendered config (and all runtime state) lives there.

**Health check note:** The spec flags `/healthz` and `/readyz` as unverified. If these endpoints don't exist in the actual image, fall back to a TCP check: `["CMD-SHELL", "nc -z localhost 18789 || exit 1"]`. Verify by pulling the image and checking its documentation or inspecting the container.

- [ ] **Step 1: Write the compose file**

Create `docker-compose.openclaw.yml`:

```yaml
services:
  openclaw-gateway:
    image: ${OPENCLAW_IMAGE:-ghcr.io/openclaw/openclaw:latest}
    container_name: openclaw-gateway
    restart: unless-stopped
    networks:
      - homeserver
    volumes:
      # All OpenClaw data: rendered config, workspace, runtime state (gitignored)
      - ./data/openclaw:/home/node/.openclaw
    # No ports published directly — Traefik proxies via Docker network
    healthcheck:
      # Note: Verify /healthz endpoint against official image before deploying.
      # If unavailable, replace with TCP check:
      #   test: ["CMD-SHELL", "nc -z localhost 18789 || exit 1"]
      test: ["CMD-SHELL", "curl -sf http://localhost:18789/healthz || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.openclaw.rule=Host(`openclaw.${DOMAIN}`)"
      - "traefik.http.routers.openclaw.entrypoints=websecure"
      - "traefik.http.routers.openclaw.tls=true"
      # Using file provider certificate (wildcard from certbot)
      - "traefik.http.services.openclaw.loadbalancer.server.port=18789"
      # Security: Apply admin-secure middleware (IP whitelist + security headers + rate limiting)
      - "traefik.http.routers.openclaw.middlewares=admin-secure"

networks:
  homeserver:
    external: true
```

- [ ] **Step 2: Validate the compose file syntax**

```bash
docker compose -f docker-compose.openclaw.yml config --quiet
```

Expected: exits 0, no output. If errors, fix syntax.

- [ ] **Step 3: Validate it works as part of the full COMPOSE stack (after Makefile update)**

This will be verified in Task 4 once the Makefile is updated. Skip for now.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.openclaw.yml
git commit -m "feat: add docker-compose.openclaw.yml"
```

---

### Task 4: Update Makefile

**Files:**
- Modify: `Makefile`

Changes required:
1. Add `logs-openclaw` to `.PHONY`
2. Update `COMPOSE` to include `docker-compose.openclaw.yml` (5th file)
3. Update `make setup`: 8→9 steps, insert Step 4/9 (OpenClaw config), renumber 4-8 → 5-9, add openclaw URL to service list
4. Add `make logs-openclaw` target
5. Add `logs-openclaw` entry under "Logs & Debugging" in `make help`

**Before making changes, note the exact current strings to match:**

- PHONY line 5: `.PHONY: logs-n8n logs-homepage`
- COMPOSE line 24: `COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml`
- setup step 4 echo (line 124): `@echo "Step 4/8: Pulling pre-built images..."`
- setup step 5 echo (line 127): `@echo "Step 5/8: Building custom services from source..."`
- setup step 6 echo (line 130): `@echo "Step 6/8: Starting services (Docker Compose will create networks)..."`
- setup step 7 echo (line 133): `@echo "Step 7/8: Fixing data directory permissions..."`
- setup step 8 echo (line 140): `@echo "Step 8/8: Configuring AdGuard DNS rewrites..."`
- service URL block ends at Alertmanager (line 175)
- logs-homepage in make help (line 54): `@echo "  make logs-homepage      - Show Homepage logs only"`

- [ ] **Step 1: Update .PHONY to add logs-openclaw**

In `Makefile` line 5, change:
```
.PHONY: logs-n8n logs-homepage
```
to:
```
.PHONY: logs-n8n logs-homepage logs-openclaw
```

- [ ] **Step 2: Update COMPOSE variable to include openclaw compose file**

Change line 24:
```
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml
```
to:
```
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.openclaw.yml
```

- [ ] **Step 3: Insert OpenClaw config as Step 4/9 in make setup, renumber 4-8 to 5-9**

Replace the block from "Step 4/8" through "Step 8/8":

Old:
```makefile
	@echo "Step 4/8: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 5/8: Building custom services from source..."
	@$(COMPOSE) build homepage-api --progress=plain
	@echo ""
	@echo "Step 6/8: Starting services (Docker Compose will create networks)..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "Step 7/8: Fixing data directory permissions..."
```

New:
```makefile
	@echo "Step 4/9: Setting up OpenClaw config..."
	@./scripts/openclaw/configure-openclaw.sh
	@echo ""
	@echo "Step 5/9: Pulling pre-built images..."
	@$(COMPOSE) pull --ignore-pull-failures
	@echo ""
	@echo "Step 6/9: Building custom services from source..."
	@$(COMPOSE) build homepage-api --progress=plain
	@echo ""
	@echo "Step 7/9: Starting services (Docker Compose will create networks)..."
	@$(COMPOSE) up -d
	@echo ""
	@echo "Step 8/9: Fixing data directory permissions..."
```

Also update steps 8/8 → 9/9:

Old:
```makefile
	@echo "Step 8/8: Configuring AdGuard DNS rewrites..."
```
New:
```makefile
	@echo "Step 9/9: Configuring AdGuard DNS rewrites..."
```

And update the total in step 1/8 and 2/8 and 3/8:

Old:
```makefile
	@echo "Step 1/8: Setting up Traefik dashboard password..."
```
New:
```makefile
	@echo "Step 1/9: Setting up Traefik dashboard password..."
```

Old:
```makefile
	@echo "Step 2/8: Setting up SSL certificate storage..."
```
New:
```makefile
	@echo "Step 2/9: Setting up SSL certificate storage..."
```

Old:
```makefile
	@echo "Step 3/8: Setting up Homepage dashboard config..."
```
New:
```makefile
	@echo "Step 3/9: Setting up Homepage dashboard config..."
```

- [ ] **Step 4: Add openclaw URL to make setup service list**

Find the Alertmanager line in the service URL block and add OpenClaw after it.

Old:
```makefile
		echo "    - Alertmanager:       https://alerts.$$DOMAIN"; \
```
New:
```makefile
		echo "    - Alertmanager:       https://alerts.$$DOMAIN"; \
		echo "    - OpenClaw AI:        https://openclaw.$$DOMAIN"; \
```

- [ ] **Step 5: Add logs-openclaw target**

After `logs-homepage` target, add:

```makefile
# Show OpenClaw gateway logs
logs-openclaw:
	@$(COMPOSE) logs -f openclaw-gateway
```

- [ ] **Step 6: Update COMPOSE_CORE comment to mention OpenClaw is excluded**

Old (Makefile line 21):
```
# COMPOSE_CORE: Core + Network + Monitoring (used for operations that shouldn't restart dashboard)
```
New:
```
# COMPOSE_CORE: Core + Network + Monitoring (used for operations that shouldn't restart dashboard or OpenClaw gateway)
```

- [ ] **Step 7: Add logs-openclaw to make help**

Find the logs-homepage line and add logs-openclaw after it:

Old:
```makefile
	@echo "  make logs-homepage      - Show Homepage logs only"
```
New:
```makefile
	@echo "  make logs-homepage      - Show Homepage logs only"
	@echo "  make logs-openclaw      - Show OpenClaw gateway logs only"
```

- [ ] **Step 8: Validate the full COMPOSE stack parses correctly**

```bash
make validate
```

Expected: `✓ Docker Compose configuration is valid`

- [ ] **Step 9: Verify make help output**

```bash
make help | grep -E "logs-openclaw|openclaw"
```

Expected: shows `make logs-openclaw - Show OpenClaw gateway logs only`

- [ ] **Step 10: Verify setup step count**

```bash
make --dry-run setup 2>/dev/null | grep "Step" | head -15
```

Expected: Steps 1/9 through 9/9, with Step 4/9 reading "Setting up OpenClaw config..."

- [ ] **Step 11: Commit**

```bash
git add Makefile
git commit -m "feat: add openclaw to COMPOSE, setup steps, and make targets"
```

---

### Task 5: Update .env.example

**Files:**
- Modify: `.env.example`

Add four new variables with documentation. These go after the existing service credentials block. Find a logical place — after the Homepage/dashboard section, before or after the monitoring vars.

- [ ] **Step 1: Add OpenClaw variables to .env.example**

Add this block at an appropriate location (after dashboard config, before monitoring/alerting vars):

```bash
# OpenClaw AI Assistant
# Accessible via https://openclaw.${DOMAIN}
# Run 'make setup' after adding these to regenerate the OpenClaw config.

# Anthropic API key for Claude model access
# Obtain from: https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Telegram bot token from @BotFather (send /newbot to @BotFather in Telegram)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Secret token for OpenClaw Control UI access
# Generate with: openssl rand -hex 32
OPENCLAW_GATEWAY_TOKEN=your_openclaw_gateway_token_here

# Optional: pin to a specific image tag (default: ghcr.io/openclaw/openclaw:latest)
# Example: OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:1.2.3
OPENCLAW_IMAGE=
```

- [ ] **Step 2: Verify all four vars are present**

```bash
grep -E "ANTHROPIC_API_KEY|TELEGRAM_BOT_TOKEN|OPENCLAW_GATEWAY_TOKEN|OPENCLAW_IMAGE" .env.example | wc -l
```

Expected: `4`

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "feat: add openclaw env vars to .env.example"
```

---

### Task 6: Update test-domain-access.sh

**Files:**
- Modify: `scripts/testing/test-domain-access.sh`

Add `test_domain "openclaw.${DOMAIN}" "OpenClaw AI Assistant"` to the test_domain call block (currently lines 194-201). Do **not** add `openclaw-gateway` to the `services=` pre-flight array at line 154 — that array causes a hard exit if the container isn't running, which would break the test for users who haven't deployed the optional `docker-compose.openclaw.yml`.

- [ ] **Step 1: Add the test_domain call**

Find the last `test_domain` call (currently `test_domain "traefik.${DOMAIN}" "Traefik Dashboard"`) and add OpenClaw after it:

Old:
```bash
test_domain "traefik.${DOMAIN}" "Traefik Dashboard"
```

New:
```bash
test_domain "traefik.${DOMAIN}" "Traefik Dashboard"
test_domain "openclaw.${DOMAIN}" "OpenClaw AI Assistant" || true
```

**Why `|| true`:** `test-domain-access.sh` has `set -e`. Without `|| true`, a failure in the openclaw test (e.g., container not deployed) would call `return 1` inside `test_domain`, which propagates to a script exit — killing the summary output. The `|| true` makes the openclaw test genuinely non-blocking for users who haven't deployed it.

- [ ] **Step 2: Verify services= array is unchanged**

```bash
grep "^services=" scripts/testing/test-domain-access.sh
```

Expected: does NOT contain `openclaw-gateway`

- [ ] **Step 3: Verify the test_domain call was added with || true**

```bash
grep "openclaw" scripts/testing/test-domain-access.sh
```

Expected: `test_domain "openclaw.${DOMAIN}" "OpenClaw AI Assistant" || true`

- [ ] **Step 4: Commit**

```bash
git add scripts/testing/test-domain-access.sh
git commit -m "feat: add openclaw domain test (non-blocking)"
```

---

### Task 7: Update SERVICES.md and CLAUDE.md

**Files:**
- Modify: `SERVICES.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update SERVICES.md — move OpenClaw from "Tried & Removed" to "Running"**

Remove the "Tried & Removed" entry for OpenClaw:

Old (in "Tried & Removed" section):
```markdown
- **[OpenClaw](https://openclaw.ai)** - AI assistant accessible via Telegram/WhatsApp/Discord. Removed due to complex Docker deployment (Homebrew in container, interactive onboarding wizard incompatible with automated container lifecycle). May be revisited if an official Docker image or env-var-based config is available.
```

Remove that line entirely.

Add an OpenClaw entry to the "Running" section under a new "AI Services" heading (or under "Core Services" — your call):

```markdown
### AI Services

#### OpenClaw
- **Purpose:** AI assistant accessible via Telegram, with Claude-powered agents
- **Access:** https://openclaw.${DOMAIN}
- **Authentication:** OPENCLAW_GATEWAY_TOKEN (Control UI) + Telegram pairing
- **Features:**
  - Claude Sonnet model via Anthropic API
  - Telegram channel with pairing-only DM policy
  - Traefik-proxied, admin-secure middleware (VPN/LAN only)
```

Also update the Quick Reference table to add OpenClaw:

Old:
```markdown
| Alertmanager | https://alerts.${DOMAIN} | http://IP:9093 |
```

New:
```markdown
| Alertmanager | https://alerts.${DOMAIN} | http://IP:9093 |
| OpenClaw     | https://openclaw.${DOMAIN} | N/A |
```

- [ ] **Step 2: Update CLAUDE.md — add OpenClaw service documentation**

In `CLAUDE.md`, under "Service-Specific Notes", add an OpenClaw section after the existing services. Add it after the "Homepage Dashboard" section:

```markdown
### OpenClaw AI Assistant
- **Purpose:** AI assistant accessible via Telegram, powered by Claude via Anthropic API
- **Image:** `${OPENCLAW_IMAGE:-ghcr.io/openclaw/openclaw:latest}` (official pre-built, no custom Dockerfile)
- **Container:** `openclaw-gateway`
- **Internal port:** 18789
- **Domain access:** `https://openclaw.${DOMAIN}`
- **Security:** admin-secure middleware (IP whitelist + rate limiting); OPENCLAW_GATEWAY_TOKEN required for Control UI
- **Config:** `data/openclaw/openclaw.json` — rendered at setup time by `scripts/openclaw/configure-openclaw.sh` using `envsubst` from `config/openclaw/openclaw.json.template`. Contains secrets — gitignored.
- **Setup pattern:** Unlike `configure-homepage.sh` (which copies templates unchanged for Homepage's runtime `{{VAR}}` resolution), `configure-openclaw.sh` uses `envsubst` to bake values in at setup time. Re-run after changing OpenClaw env vars: `./scripts/openclaw/configure-openclaw.sh && docker compose restart openclaw-gateway`
- **Data persistence:** `./data/openclaw/` — config, workspace, session data, cron runs (all gitignored)
- **Compose file:** `docker-compose.openclaw.yml` (5th file, included in `COMPOSE`, excluded from `COMPOSE_CORE`)
- **Required env vars:** `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `OPENCLAW_GATEWAY_TOKEN`
- **Optional env var:** `OPENCLAW_IMAGE` — pin to a specific image tag
- **Telegram setup:** After `make setup`, send `/start` to the bot in Telegram to pair
```

Also update the "Multi-File Docker Compose" section in CLAUDE.md to mention the 5th file:

Old:
```
The stack uses **four compose files** organized by logical function:
- `docker-compose.yml` - Core services (AdGuard, n8n) - user-facing services that "do stuff"
- `docker-compose.network.yml` - Network & Security (Traefik, Fail2ban) - infrastructure layer
- `docker-compose.monitoring.yml` - Monitoring stack (Prometheus, Grafana, Alertmanager, exporters)
- `docker-compose.dashboard.yml` - Dashboard (Homepage, Homepage API)
```

New:
```
The stack uses **five compose files** organized by logical function:
- `docker-compose.yml` - Core services (AdGuard, n8n) - user-facing services that "do stuff"
- `docker-compose.network.yml` - Network & Security (Traefik, Fail2ban) - infrastructure layer
- `docker-compose.monitoring.yml` - Monitoring stack (Prometheus, Grafana, Alertmanager, exporters)
- `docker-compose.dashboard.yml` - Dashboard (Homepage, Homepage API)
- `docker-compose.openclaw.yml` - OpenClaw AI assistant
```

Also update the Makefile comment block near the top of CLAUDE.md (the `COMPOSE_CORE` / `COMPOSE` note):

Old:
```
The Makefile combines all files by default: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml`
```

New:
```
The Makefile combines all files by default: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.openclaw.yml`
```

- [ ] **Step 3: Verify SERVICES.md no longer lists OpenClaw under "Tried & Removed"**

```bash
grep -A2 "Tried & Removed" SERVICES.md | grep -c "OpenClaw" && echo "FAIL: still in Tried & Removed" || echo "PASS: removed from Tried & Removed"
```

- [ ] **Step 4: Verify SERVICES.md has OpenClaw in Running section**

```bash
grep "OpenClaw" SERVICES.md
```

Expected: entry in Running section and Quick Reference table.

- [ ] **Step 5: Commit**

```bash
git add SERVICES.md CLAUDE.md
git commit -m "docs: add openclaw to running services and CLAUDE.md"
```

---

### Task 8: Full integration validation

No new files. Validates everything wires together correctly.

- [ ] **Step 1: Validate full compose config**

```bash
make validate
```

Expected: `✓ Docker Compose configuration is valid`

- [ ] **Step 2: Verify the configure script renders correctly with real (or test) values**

If the real values are in `.env`:
```bash
./scripts/openclaw/configure-openclaw.sh
cat data/openclaw/openclaw.json
```

Confirm no `${...}` remains in output.

- [ ] **Step 3: Verify all make targets exist**

```bash
make help | grep openclaw
```

Expected: `make logs-openclaw - Show OpenClaw gateway logs only`

- [ ] **Step 4: Verify make setup step count and ordering**

```bash
grep -n "Step [0-9]/9" Makefile
```

Expected: Steps 1/9 through 9/9, with Step 4/9 being OpenClaw config.

- [ ] **Step 5: Verify test-domain-access.sh has openclaw test but not in services= array**

```bash
grep "openclaw" scripts/testing/test-domain-access.sh
grep "^services=" scripts/testing/test-domain-access.sh
```

Expected:
- Line 1: `test_domain "openclaw.${DOMAIN}" "OpenClaw AI Assistant" || true`
- Line 2: services= array does NOT contain `openclaw-gateway`

- [ ] **Step 6: Verify .env.example has all four openclaw vars**

```bash
grep -E "ANTHROPIC_API_KEY|TELEGRAM_BOT_TOKEN|OPENCLAW_GATEWAY_TOKEN|OPENCLAW_IMAGE" .env.example
```

Expected: 4 lines.

- [ ] **Step 7: Verify data/openclaw is gitignored**

```bash
echo "data/openclaw/test" | git check-ignore --stdin
```

Expected: `data/openclaw/test` (the `data/` top-level gitignore covers it)

- [ ] **Step 8: Final commit and push**

```bash
git push origin feature/openclaw-docker
```

Then open a PR from `feature/openclaw-docker` → `main`.

---

## First-Time Usage (after deployment)

1. Add to `.env`: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `OPENCLAW_GATEWAY_TOKEN`
2. `make setup` (or `./scripts/openclaw/configure-openclaw.sh && make start`)
3. Visit `https://openclaw.${DOMAIN}` → log in with `OPENCLAW_GATEWAY_TOKEN`
4. Send `/start` to your Telegram bot to pair
