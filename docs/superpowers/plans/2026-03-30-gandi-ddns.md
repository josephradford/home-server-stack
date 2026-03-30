# Gandi LiveDNS Dynamic DNS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace No-IP DDNS with a self-hosted solution that keeps `vpn.DOMAIN` pointing at the server's current public IP using the Gandi LiveDNS API and a user crontab entry.

**Architecture:** Two bash scripts — `gandi-ddns-update.sh` runs every 5 minutes via cron to check and update the DNS record; `setup-gandi-ddns.sh` is run once to create the initial record, install the cron entry, and configure log rotation. Three Makefile targets wire these up. Reuses existing `GANDIV5_PERSONAL_ACCESS_TOKEN` and `DOMAIN` from `.env`.

**Tech Stack:** bash, curl, jq, Gandi LiveDNS API v5, user crontab, logrotate

**Spec:** `docs/superpowers/specs/2026-03-30-gandi-ddns-design.md`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `scripts/ddns/gandi-ddns-update.sh` | Fetch public IP, compare to Gandi record, PUT if changed |
| Create | `scripts/ddns/setup-gandi-ddns.sh` | One-time setup: create DNS record, install cron, configure logrotate |
| Modify | `Makefile` | Add `.PHONY` + `ddns-setup`, `ddns-update`, `ddns-status` targets; update `wireguard-setup` next steps; update `help` |
| Modify | `.env.example` | Add `WIREGUARD_DDNS_SUBDOMAIN=vpn`; update `WIREGUARD_SERVERURL` comment |

---

## Task 1: `gandi-ddns-update.sh` — scaffold and validation

**Files:**
- Create: `scripts/ddns/gandi-ddns-update.sh`

- [ ] **Step 1: Create the script with boilerplate and variable validation**

```bash
#!/bin/bash
# gandi-ddns-update.sh
# Checks current public IP against Gandi LiveDNS A record and updates if changed.
# Run every 5 minutes via cron (installed by setup-gandi-ddns.sh).

set -e

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

if [ ! -f "$ENV_FILE" ]; then
    log "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# Validate required variables
for var in DOMAIN GANDIV5_PERSONAL_ACCESS_TOKEN WIREGUARD_DDNS_SUBDOMAIN; do
    if [ -z "${!var}" ]; then
        log "ERROR: $var not set in $ENV_FILE"
        exit 1
    fi
done

GANDI_API="https://api.gandi.net/v5/livedns"
AUTH_HEADER="Authorization: Bearer $GANDIV5_PERSONAL_ACCESS_TOKEN"
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/ddns/gandi-ddns-update.sh
```
Expected: no output (clean parse)

- [ ] **Step 3: Make executable and commit**

```bash
chmod +x scripts/ddns/gandi-ddns-update.sh
git add scripts/ddns/gandi-ddns-update.sh
git commit -m "feat: add gandi-ddns-update.sh scaffold with variable validation"
```

---

## Task 2: `gandi-ddns-update.sh` — public IP fetching

**Files:**
- Modify: `scripts/ddns/gandi-ddns-update.sh`

- [ ] **Step 1: Add IP fetch function after the variable validation block**

```bash
# Fetch current public IP with fallback.
# The `|| true` at the end prevents set -e from exiting on curl failure —
# the regex check below handles the empty/invalid result explicitly.
get_public_ip() {
    local ip
    ip=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null) \
        || ip=$(curl -sf --max-time 5 ipinfo.io/ip 2>/dev/null) \
        || true

    # Validate IPv4 format
    if [[ ! "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
        log "ERROR: Could not fetch a valid public IP (got: '${ip:-empty}')"
        exit 1
    fi
    echo "$ip"
}

CURRENT_IP=$(get_public_ip)
log "Public IP: $CURRENT_IP"
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/ddns/gandi-ddns-update.sh
```

- [ ] **Step 3: Smoke test the IP fetch in isolation**

```bash
bash -c '
    get_public_ip() {
        local ip
        ip=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null) \
            || ip=$(curl -sf --max-time 5 ipinfo.io/ip 2>/dev/null) \
            || true
        if [[ ! "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
            echo "FAIL: bad IP: ${ip:-empty}"; exit 1
        fi
        echo "$ip"
    }
    get_public_ip
'
```
Expected: prints your current public IP address

- [ ] **Step 4: Commit**

```bash
git add scripts/ddns/gandi-ddns-update.sh
git commit -m "feat: add public IP fetch with IPv4 validation and fallback"
```

---

## Task 3: `gandi-ddns-update.sh` — Gandi GET and comparison

**Files:**
- Modify: `scripts/ddns/gandi-ddns-update.sh`

- [ ] **Step 1: Add GET logic after the IP fetch block**

```bash
# Fetch current A record from Gandi.
# Response body is written to a temp file; only the HTTP status code is captured
# in the variable. This avoids line-splitting issues with multi-line JSON bodies.
RECORD_URL="$GANDI_API/domains/$DOMAIN/records/$WIREGUARD_DDNS_SUBDOMAIN/A"

HTTP_STATUS=$(curl -s -o /tmp/gandi-ddns-response.json -w "%{http_code}" \
    -H "$AUTH_HEADER" \
    "$RECORD_URL")

case "$HTTP_STATUS" in
    200)
        GANDI_IP=$(jq -r '.rrset_values[0]' /tmp/gandi-ddns-response.json)
        log "Gandi record: $GANDI_IP"
        ;;
    404)
        log "No existing record found — will create"
        GANDI_IP=""
        ;;
    *)
        log "ERROR: Gandi GET returned HTTP $HTTP_STATUS"
        jq . /tmp/gandi-ddns-response.json 2>/dev/null || cat /tmp/gandi-ddns-response.json
        exit 1
        ;;
esac

# Skip update if IP unchanged
if [ "$CURRENT_IP" = "$GANDI_IP" ]; then
    log "IP unchanged ($CURRENT_IP), skipping"
    exit 0
fi
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/ddns/gandi-ddns-update.sh
```

- [ ] **Step 3: Test the GET against the real API (read-only)**

Requires `.env` to be populated with real values. If `vpn.DOMAIN` doesn't exist yet, expect a 404 — that is correct behaviour.

```bash
source .env
curl -s \
    -H "Authorization: Bearer $GANDIV5_PERSONAL_ACCESS_TOKEN" \
    "https://api.gandi.net/v5/livedns/domains/$DOMAIN/records/$WIREGUARD_DDNS_SUBDOMAIN/A" \
    | jq .
```
Expected: either `{"rrset_values": ["x.x.x.x"], ...}` or a 404 error body

- [ ] **Step 4: Commit**

```bash
git add scripts/ddns/gandi-ddns-update.sh
git commit -m "feat: add Gandi GET with 404 handling and IP comparison"
```

---

## Task 4: `gandi-ddns-update.sh` — Gandi PUT

**Files:**
- Modify: `scripts/ddns/gandi-ddns-update.sh`

- [ ] **Step 1: Add PUT logic after the comparison block**

```bash
# Update Gandi record
log "Updating $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP"

HTTP_STATUS=$(curl -s -o /tmp/gandi-ddns-response.json -w "%{http_code}" \
    -X PUT \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "{\"rrset_values\": [\"$CURRENT_IP\"], \"rrset_ttl\": 300}" \
    "$RECORD_URL")

case "$HTTP_STATUS" in
    201|204)
        log "Updated $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP"
        ;;
    *)
        log "ERROR: Gandi PUT returned HTTP $HTTP_STATUS"
        jq . /tmp/gandi-ddns-response.json 2>/dev/null || cat /tmp/gandi-ddns-response.json
        exit 1
        ;;
esac
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/ddns/gandi-ddns-update.sh
```

- [ ] **Step 3: End-to-end dry run (verify the full script without triggering a PUT)**

Comment out the PUT `curl` call temporarily, source `.env`, then run:
```bash
bash scripts/ddns/gandi-ddns-update.sh
```
Expected: `[timestamp] Public IP: x.x.x.x` then either "IP unchanged, skipping" or "No existing record found — will create", then exit 0

Restore the PUT block.

- [ ] **Step 4: Commit**

```bash
git add scripts/ddns/gandi-ddns-update.sh
git commit -m "feat: add Gandi PUT to complete update script"
```

---

## Task 5: `setup-gandi-ddns.sh`

**Files:**
- Create: `scripts/ddns/setup-gandi-ddns.sh`

- [ ] **Step 1: Write the full setup script**

```bash
#!/bin/bash
# setup-gandi-ddns.sh
# One-time setup: creates vpn.DOMAIN A record in Gandi LiveDNS, installs a
# user crontab entry to run gandi-ddns-update.sh every 5 minutes, and
# configures log rotation.
#
# Run from the repo root: sudo ./scripts/ddns/setup-gandi-ddns.sh
# (sudo required for /var/log/ and /etc/logrotate.d/ write access)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "Gandi LiveDNS Dynamic DNS Setup"
echo "================================="
echo ""

# Must be run with sudo
if [ "$(id -u)" != "0" ]; then
    echo -e "${RED}ERROR: Run with sudo${NC}"
    echo "  sudo ./scripts/ddns/setup-gandi-ddns.sh"
    exit 1
fi

# Identify the real user (not root).
# $SUDO_USER is set by sudo to the original unprivileged username.
REAL_USER="${SUDO_USER:-$(whoami)}"

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: .env not found at $ENV_FILE${NC}"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

# Validate required variables
for var in DOMAIN GANDIV5_PERSONAL_ACCESS_TOKEN WIREGUARD_DDNS_SUBDOMAIN; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}ERROR: $var not set in .env${NC}"
        exit 1
    fi
done

# Check jq is installed
if ! command -v jq &>/dev/null; then
    echo -e "${RED}ERROR: jq is required but not installed${NC}"
    echo "Install with: sudo apt-get install -y jq"
    exit 1
fi

GANDI_API="https://api.gandi.net/v5/livedns"
AUTH_HEADER="Authorization: Bearer $GANDIV5_PERSONAL_ACCESS_TOKEN"
RECORD_URL="$GANDI_API/domains/$DOMAIN/records/$WIREGUARD_DDNS_SUBDOMAIN/A"
# Note: spec uses `realpath scripts/ddns/gandi-ddns-update.sh` (CWD-relative).
# Using $REPO_ROOT derived from BASH_SOURCE is more robust — it works regardless
# of the working directory the script is invoked from.
UPDATE_SCRIPT="$REPO_ROOT/scripts/ddns/gandi-ddns-update.sh"
LOG_FILE="/var/log/gandi-ddns.log"

# Step 1: Fetch public IP
echo -e "${YELLOW}Step 1/4: Fetching current public IP...${NC}"
# The `|| true` prevents set -e from exiting on curl failure;
# the regex check below handles the empty/invalid result explicitly.
CURRENT_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null) \
    || CURRENT_IP=$(curl -sf --max-time 5 ipinfo.io/ip 2>/dev/null) \
    || true

if [[ ! "$CURRENT_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
    echo -e "${RED}ERROR: Could not fetch a valid public IP (got: '${CURRENT_IP:-empty}')${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Public IP: $CURRENT_IP"
echo ""

# Step 2: Create/update A record in Gandi
echo -e "${YELLOW}Step 2/4: Creating $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP...${NC}"
HTTP_STATUS=$(curl -s -o /tmp/gandi-ddns-setup.json -w "%{http_code}" \
    -X PUT \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d "{\"rrset_values\": [\"$CURRENT_IP\"], \"rrset_ttl\": 300}" \
    "$RECORD_URL")

if [ "$HTTP_STATUS" = "201" ] || [ "$HTTP_STATUS" = "204" ]; then
    echo -e "${GREEN}✓${NC} DNS record created: $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP"
else
    echo -e "${RED}ERROR: Gandi API returned HTTP $HTTP_STATUS${NC}"
    jq . /tmp/gandi-ddns-setup.json 2>/dev/null || cat /tmp/gandi-ddns-setup.json
    exit 1
fi
echo ""

# Step 3: Create log file owned by the real user so the cron job can append to it.
# Running as sudo, we must explicitly chown back to $REAL_USER after creation.
echo -e "${YELLOW}Step 3/4: Creating log file and configuring log rotation...${NC}"
touch "$LOG_FILE"
chown "$REAL_USER": "$LOG_FILE"
chmod 644 "$LOG_FILE"
echo -e "${GREEN}✓${NC} Log file: $LOG_FILE (owner: $REAL_USER)"

cat > /etc/logrotate.d/gandi-ddns <<EOF
$LOG_FILE {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
echo -e "${GREEN}✓${NC} Log rotation configured"
echo ""

# Step 4: Install cron entry for the real user (idempotent).
# Uses `crontab -u $REAL_USER` because the script runs as root via sudo —
# plain `crontab -` would install into root's crontab instead.
# Deduplication key is "gandi-ddns-update.sh": any existing entry with that
# filename is removed before the new line is appended.
echo -e "${YELLOW}Step 4/4: Installing cron entry...${NC}"
CRON_LINE="*/5 * * * * $UPDATE_SCRIPT >> $LOG_FILE 2>&1"
(crontab -u "$REAL_USER" -l 2>/dev/null | grep -v "gandi-ddns-update.sh"; \
 echo "$CRON_LINE") | crontab -u "$REAL_USER" -
echo -e "${GREEN}✓${NC} Cron entry installed for $REAL_USER (every 5 minutes)"
echo ""

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "DNS record created:"
echo "  $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP (TTL 300s)"
echo ""
echo "Cron job installed for user: $REAL_USER"
echo "  Runs every 5 minutes"
echo "  Logs to: $LOG_FILE"
echo ""
echo "Next steps:"
echo "  1. Update your .env:  WIREGUARD_SERVERURL=$WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN"
echo "  2. Test the updater:  make ddns-update"
echo "  3. Check status:      make ddns-status"
echo ""
echo "Action required — regenerate configs for existing WireGuard peers"
echo "so their Endpoint uses the hostname instead of a raw IP (one-time only):"
echo "  sudo ./scripts/wireguard/wireguard-add-peer.sh <peer-name>"
echo ""
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x scripts/ddns/setup-gandi-ddns.sh
bash -n scripts/ddns/setup-gandi-ddns.sh
```
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add scripts/ddns/setup-gandi-ddns.sh
git commit -m "feat: add setup-gandi-ddns.sh"
```

---

## Task 6: Makefile targets

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add `ddns-*` to `.PHONY` after the ssl line (line 8)**

```makefile
.PHONY: ssl-setup ssl-renew-test
.PHONY: ddns-setup ddns-update ddns-status
```

- [ ] **Step 2: Add the three targets after the `wireguard-test` block**

```makefile
ddns-setup:
	@echo "Setting up Gandi LiveDNS dynamic DNS..."
	@echo ""
	@sudo ./scripts/ddns/setup-gandi-ddns.sh

ddns-update:
	@echo "Running Gandi DDNS update check..."
	@./scripts/ddns/gandi-ddns-update.sh

ddns-status:
	@set -a; . ./.env; set +a; \
	CURRENT_IP=$$(curl -sf --max-time 5 ifconfig.me 2>/dev/null \
	    || curl -sf --max-time 5 ipinfo.io/ip 2>/dev/null \
	    || echo "unavailable"); \
	HTTP_STATUS=$$(curl -s -o /tmp/gandi-ddns-status.json -w "%{http_code}" \
	    -H "Authorization: Bearer $$GANDIV5_PERSONAL_ACCESS_TOKEN" \
	    "https://api.gandi.net/v5/livedns/domains/$$DOMAIN/records/$$WIREGUARD_DDNS_SUBDOMAIN/A"); \
	if [ "$$HTTP_STATUS" = "200" ]; then \
	    GANDI_IP=$$(jq -r '.rrset_values[0]' /tmp/gandi-ddns-status.json); \
	else \
	    GANDI_IP="(no record found)"; \
	fi; \
	echo "DDNS Status"; \
	echo "  Current public IP:  $$CURRENT_IP"; \
	echo "  Gandi DNS record:   $$GANDI_IP ($$WIREGUARD_DDNS_SUBDOMAIN.$$DOMAIN)"; \
	if [ "$$CURRENT_IP" = "$$GANDI_IP" ]; then \
	    echo "  Status: in sync"; \
	else \
	    echo "  Status: out of sync — run: make ddns-update"; \
	fi
```

Note: `ddns-status` uses `-o /tmp/gandi-ddns-status.json -w "%{http_code}"` to capture body and status separately, avoiding multi-line JSON parsing issues.

- [ ] **Step 3: Update `wireguard-setup` next steps (around line 395)**

Add after the existing step 3:
```makefile
	@echo ""
	@echo "Optional — if your public IP is dynamic:"
	@echo "  Set WIREGUARD_DDNS_SUBDOMAIN=vpn in .env, then:"
	@echo "  4. Set up automatic DNS:   make ddns-setup"
```

- [ ] **Step 4: Update the `help` target to list the new DDNS targets**

Find the WireGuard section in the `help` target and add after it:
```makefile
	@echo "  make ddns-setup     - Create vpn.DOMAIN DNS record and install 5-min cron updater"
	@echo "  make ddns-update    - Manually trigger a DDNS IP check and update"
	@echo "  make ddns-status    - Show current public IP vs Gandi DNS record"
```

- [ ] **Step 5: Verify Makefile syntax with a dry run**

```bash
make -n ddns-status
```
Expected: prints the shell commands that would run, no errors

- [ ] **Step 6: Commit**

```bash
git add Makefile
git commit -m "feat: add ddns Makefile targets and wireguard-setup DDNS hint"
```

---

## Task 7: `.env.example` updates

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Replace the `WIREGUARD_SERVERURL` block in the WireGuard section**

```bash
# Public hostname or IP that VPN clients use to connect from outside your home network.
# If using Gandi DDNS (make ddns-setup), set this to: vpn.DOMAIN
# If you have a static public IP, set this to the IP directly.
# Get your current public IP with: curl ifconfig.me
# Requires port forwarding on your router: WIREGUARD_PORT/UDP → SERVER_IP
WIREGUARD_SERVERURL=vpn.your-domain.com

# Subdomain for dynamic DNS (managed by make ddns-setup).
# Creates a vpn.DOMAIN A record pointing at your public IP, updated every 5 minutes.
# Only needed if your ISP assigns a dynamic public IP.
WIREGUARD_DDNS_SUBDOMAIN=vpn
```

- [ ] **Step 2: Verify the file parses cleanly**

```bash
bash -c 'set -a; source .env.example; set +a; echo "OK"'
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "feat: add WIREGUARD_DDNS_SUBDOMAIN to .env.example"
```

---

## Task 8: Integration test

Run these steps on the actual home server (not the dev machine).

- [ ] **Step 1: Ensure `.env` has the required variables set**

```bash
grep -E "WIREGUARD_DDNS_SUBDOMAIN|GANDIV5_PERSONAL_ACCESS_TOKEN|DOMAIN" .env
```
Expected: all three variables present and non-empty

- [ ] **Step 2: Check jq is installed**

```bash
jq --version
```
If missing: `sudo apt-get install -y jq`

- [ ] **Step 3: Run setup**

```bash
make ddns-setup
```
Expected: 4-step output ending with "Setup Complete!" and next steps printed

- [ ] **Step 4: Verify log file ownership**

```bash
ls -la /var/log/gandi-ddns.log
```
Expected: file is owned by your non-root user (not root), mode `-rw-r--r--`

- [ ] **Step 5: Verify logrotate config was written**

```bash
cat /etc/logrotate.d/gandi-ddns
```
Expected: config block referencing `/var/log/gandi-ddns.log` with daily/rotate 7/compress

- [ ] **Step 6: Verify cron entry was installed**

```bash
crontab -l | grep gandi-ddns
```
Expected: `*/5 * * * * /path/to/scripts/ddns/gandi-ddns-update.sh >> /var/log/gandi-ddns.log 2>&1`

- [ ] **Step 7: Verify DNS record in Gandi**

```bash
make ddns-status
```
Expected: public IP and Gandi record match, status shows "in sync"

- [ ] **Step 8: Manually trigger the updater**

```bash
make ddns-update
```
Expected: `[timestamp] IP unchanged (x.x.x.x), skipping`

- [ ] **Step 9: Wait ~5 minutes and verify cron ran**

```bash
tail -20 /var/log/gandi-ddns.log
```
Expected: at least one cron-triggered "IP unchanged, skipping" entry

- [ ] **Step 10: Final commit**

```bash
git add .
git commit -m "feat: complete Gandi LiveDNS DDNS implementation"
```
