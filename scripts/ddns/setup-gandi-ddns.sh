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
