#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Configuring Moltbot for reverse proxy access...${NC}"

# Path to moltbot config
CONFIG_FILE="./data/moltbot/.clawdbot/moltbot.json"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Moltbot config not found at $CONFIG_FILE${NC}"
    echo "Please run 'make moltbot-onboard' first to initialize Moltbot"
    exit 1
fi

# Stop the gateway if it's running (prevents config from being overwritten)
echo "Stopping moltbot-gateway (if running)..."
docker compose stop moltbot-gateway 2>/dev/null || true

# Backup the config
BACKUP_FILE="${CONFIG_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo -e "${GREEN}✓${NC} Backed up config to $BACKUP_FILE"

# Add trustedProxies to gateway section using Python
python3 <<'PYTHON'
import json
import sys

config_file = "./data/moltbot/.clawdbot/moltbot.json"

try:
    # Read current config
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Ensure gateway section exists
    if 'gateway' not in config:
        config['gateway'] = {}

    # Add trustedProxies array with Docker bridge network
    # This allows Moltbot to trust proxy headers from Traefik
    config['gateway']['trustedProxies'] = ['172.18.0.0/16']

    # Write updated config with proper formatting
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print("✓ Added trustedProxies configuration to gateway section")

except Exception as e:
    print(f"✗ Error updating config: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Configured Moltbot to trust Traefik reverse proxy (172.18.0.0/16)"
    echo ""
    echo -e "${BLUE}What this does:${NC}"
    echo "  - Allows Moltbot to trust X-Forwarded-For headers from Traefik"
    echo "  - Enables proper client IP detection behind the reverse proxy"
    echo "  - Fixes 'Proxy headers detected from untrusted address' warnings"
    echo ""

    # Verify the change was written
    if grep -q '"trustedProxies"' "$CONFIG_FILE"; then
        echo -e "${GREEN}✓${NC} Verified trustedProxies added to config"
    else
        echo -e "${RED}✗${NC} Warning: trustedProxies not found in config after update"
        echo "This may indicate a problem with the configuration"
    fi

    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Start moltbot-gateway: ${YELLOW}docker compose up -d moltbot-gateway${NC}"
    echo "  2. Check logs: ${YELLOW}docker logs moltbot-gateway --tail 50${NC}"
    echo "  3. Verify config persisted: ${YELLOW}docker exec moltbot-gateway cat /home/node/.clawdbot/moltbot.json | grep trustedProxies${NC}"
    echo "  4. Access web UI: ${YELLOW}https://moltbot.\${DOMAIN}${NC}"
    echo ""
else
    echo -e "${RED}✗${NC} Failed to configure Moltbot"
    echo "Restoring backup from $BACKUP_FILE"
    cp "$BACKUP_FILE" "$CONFIG_FILE"
    docker compose up -d moltbot-gateway 2>/dev/null || true
    exit 1
fi
