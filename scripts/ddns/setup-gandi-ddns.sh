#!/bin/bash
# setup-gandi-ddns.sh
# One-time setup: creates vpn.DOMAIN A record in Gandi LiveDNS and installs
# a systemd timer to run gandi-ddns-update.sh every 5 minutes.
#
# Run from the repo root: sudo ./scripts/ddns/setup-gandi-ddns.sh
# (sudo required for systemd unit installation)

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
UPDATE_SCRIPT="$REPO_ROOT/scripts/ddns/gandi-ddns-update.sh"

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

# Step 3: Remove legacy cron entry if present
echo -e "${YELLOW}Step 3/5: Removing legacy cron entry (if any)...${NC}"
REAL_USER="${SUDO_USER:-$(whoami)}"
if crontab -u "$REAL_USER" -l 2>/dev/null | grep -q "gandi-ddns-update.sh"; then
    crontab -u "$REAL_USER" -l 2>/dev/null | grep -v "gandi-ddns-update.sh" | crontab -u "$REAL_USER" -
    echo -e "${GREEN}✓${NC} Removed legacy cron entry"
else
    echo -e "${GREEN}✓${NC} No legacy cron entry found"
fi
echo ""

# Step 4: Install systemd timer
echo -e "${YELLOW}Step 4/5: Installing systemd timer...${NC}"
sed "s|__REPO_ROOT__|$REPO_ROOT|g" "$SCRIPT_DIR/gandi-ddns.service" > /etc/systemd/system/gandi-ddns.service
cp "$SCRIPT_DIR/gandi-ddns.timer" /etc/systemd/system/gandi-ddns.timer
systemctl daemon-reload
systemctl enable --now gandi-ddns.timer
echo -e "${GREEN}✓${NC} Systemd timer installed and started"
echo ""

# Step 5: Verify timer is active
echo -e "${YELLOW}Step 5/5: Verifying timer...${NC}"
if systemctl is-active --quiet gandi-ddns.timer; then
    echo -e "${GREEN}✓${NC} gandi-ddns.timer is active"
    NEXT_RUN=$(systemctl show gandi-ddns.timer --property=NextElapseUSecRealtime --value)
    echo -e "${GREEN}✓${NC} Next run: $NEXT_RUN"
else
    echo -e "${RED}ERROR: gandi-ddns.timer failed to start${NC}"
    systemctl status gandi-ddns.timer
    exit 1
fi
echo ""

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "DNS record created:"
echo "  $WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN → $CURRENT_IP (TTL 300s)"
echo ""
echo "Systemd timer installed:"
echo "  Runs every 5 minutes (+ 30s after boot)"
echo "  Logs: journalctl -u gandi-ddns"
echo "  Status: systemctl status gandi-ddns.timer"
echo ""
echo "Next steps:"
echo "  1. Update your .env:  WIREGUARD_SERVERURL=$WIREGUARD_DDNS_SUBDOMAIN.$DOMAIN"
echo "  2. Test the updater:  make ddns-update"
echo "  3. Check status:      make ddns-status"
echo ""
