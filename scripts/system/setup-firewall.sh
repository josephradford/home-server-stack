#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}UFW Firewall Setup for Home Server Stack${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Verify required variables
if [ -z "$WIREGUARD_PORT" ]; then
    WIREGUARD_PORT=51820
    echo -e "${YELLOW}WIREGUARD_PORT not set, using default: 51820${NC}"
fi

if [ -z "$WIREGUARD_SUBNET" ]; then
    WIREGUARD_SUBNET="10.13.13.0/24"
    echo -e "${YELLOW}WIREGUARD_SUBNET not set, using default: 10.13.13.0/24${NC}"
fi

echo -e "${YELLOW}⚠️  This will reset and reconfigure UFW firewall${NC}"
echo -e "${YELLOW}⚠️  Make sure you're not locked out (SSH will be allowed)${NC}"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo -e "${GREEN}Step 0/7: Installing UFW if not present...${NC}"
if ! command -v ufw &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y ufw
    echo -e "${GREEN}✓ UFW installed${NC}"
else
    echo -e "${GREEN}✓ UFW already installed${NC}"
fi

echo ""
echo -e "${GREEN}Step 1/7: Resetting UFW to default configuration...${NC}"
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

echo ""
echo -e "${GREEN}Step 2/7: Allowing SSH (port 22)...${NC}"
sudo ufw allow 22/tcp comment 'SSH'
# SSH brute-force protection handled by system fail2ban (setup-fail2ban.sh)
# which supports ignoreip for local/VPN subnets. UFW limit is too blunt
# (hardcoded 6 conns/30s, no whitelist).

echo ""
echo -e "${GREEN}Step 3/7: Allowing WireGuard VPN (port ${WIREGUARD_PORT})...${NC}"
sudo ufw allow ${WIREGUARD_PORT}/udp comment 'WireGuard VPN'

echo ""
echo -e "${GREEN}Step 4/7: Allowing HTTP/HTTPS for Traefik...${NC}"
sudo ufw allow 80/tcp comment 'HTTP for Traefik'
sudo ufw allow 443/tcp comment 'HTTPS for Traefik'

echo ""
echo -e "${GREEN}Step 5/7: Allowing local network access (192.168.1.0/24)...${NC}"
sudo ufw allow from 192.168.1.0/24 comment 'Local Network'

echo ""
echo -e "${GREEN}Step 6/7: Allowing WireGuard VPN clients (${WIREGUARD_SUBNET})...${NC}"
sudo ufw allow from ${WIREGUARD_SUBNET} comment 'WireGuard Clients'

echo ""
echo -e "${GREEN}Step 7/7: Enabling UFW...${NC}"
sudo ufw --force enable

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ UFW Firewall Configuration Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Current UFW Status:${NC}"
sudo ufw status verbose
echo ""
echo -e "${YELLOW}Security Notes:${NC}"
echo "  • SSH brute-force protection via system fail2ban (run setup-fail2ban.sh)"
echo "  • Only WireGuard (UDP ${WIREGUARD_PORT}) is exposed to the internet"
echo "  • HTTP/HTTPS (80/443) are open for Traefik reverse proxy"
echo "  • Local network and VPN clients have full access"
echo ""
echo -e "${YELLOW}To check firewall status later: ${NC}sudo ufw status verbose"
echo -e "${YELLOW}To temporarily disable: ${NC}sudo ufw disable"
echo -e "${YELLOW}To manually ban an IP: ${NC}sudo ufw deny from <IP>"
