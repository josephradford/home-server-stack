#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}System Fail2ban Setup for SSH Protection${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "This installs system-level fail2ban for SSH brute-force protection."
echo "It replaces UFW's hardcoded rate limit with a configurable jail that"
echo "ignores local network and VPN subnets."
echo ""

# Load environment variables for subnet config
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

WIREGUARD_SUBNET="${WIREGUARD_SUBNET:-10.13.13.0/24}"

echo -e "${GREEN}Step 1/4: Installing fail2ban...${NC}"
if ! command -v fail2ban-client &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y fail2ban
    echo -e "${GREEN}✓ fail2ban installed${NC}"
else
    echo -e "${GREEN}✓ fail2ban already installed${NC}"
fi

echo ""
echo -e "${GREEN}Step 2/4: Removing UFW SSH rate limit (fail2ban takes over)...${NC}"
if sudo ufw status | grep -q 'LIMIT'; then
    sudo ufw delete limit ssh/tcp 2>/dev/null || true
    echo -e "${GREEN}✓ UFW SSH rate limit removed${NC}"
else
    echo -e "${GREEN}✓ No UFW SSH rate limit to remove${NC}"
fi

echo ""
echo -e "${GREEN}Step 3/4: Configuring sshd jail...${NC}"
sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
ignoreip = 127.0.0.1/8 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 10
findtime = 5m
bantime = 30m
EOF
echo -e "${GREEN}✓ /etc/fail2ban/jail.local written${NC}"
echo "  sshd jail: 10 failed attempts in 5 minutes → 30 minute ban"
echo "  Ignored: localhost, RFC1918 (local net), WireGuard subnet"

echo ""
echo -e "${GREEN}Step 4/4: Enabling and starting fail2ban...${NC}"
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ System fail2ban configured!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
sudo fail2ban-client status sshd
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  sudo fail2ban-client status sshd        # Check jail status"
echo "  sudo fail2ban-client set sshd unbanip IP # Unban an IP"
echo "  sudo fail2ban-client get sshd maxretry   # Check threshold"
