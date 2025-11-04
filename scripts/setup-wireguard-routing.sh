#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}WireGuard VPN Routing Setup${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Detect primary network interface (interface with default route)
LAN_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
if [ -z "$LAN_INTERFACE" ]; then
    echo -e "${RED}Error: Could not detect primary network interface${NC}"
    exit 1
fi

echo -e "${YELLOW}Detected LAN interface: ${LAN_INTERFACE}${NC}"
echo ""

# Get Docker bridge network from WireGuard container
DOCKER_NETWORK=$(docker network inspect home-server-stack_homeserver -f '{{(index .IPAM.Config 0).Subnet}}' 2>/dev/null || echo "")
if [ -z "$DOCKER_NETWORK" ]; then
    echo -e "${YELLOW}Warning: WireGuard Docker network not found. Will use default 172.18.0.0/16${NC}"
    echo -e "${YELLOW}Start WireGuard first, then re-run this script for accurate detection.${NC}"
    DOCKER_NETWORK="172.18.0.0/16"
fi

echo -e "${YELLOW}Docker network: ${DOCKER_NETWORK}${NC}"
echo ""

# VPN subnet
VPN_SUBNET="${WIREGUARD_SUBNET:-10.13.13.0/24}"
echo -e "${YELLOW}VPN subnet: ${VPN_SUBNET}${NC}"
echo ""

echo -e "${GREEN}This script will set up iptables rules for WireGuard VPN routing:${NC}"
echo "  1. Allow forwarding from Docker network to LAN"
echo "  2. Allow forwarding from LAN to Docker network (return traffic)"
echo "  3. Enable NAT for VPN traffic to LAN"
echo ""
echo "These rules allow VPN clients to access your local network (192.168.1.0/24)"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo ""
echo -e "${GREEN}Step 1/3: Adding iptables FORWARD rules...${NC}"

# Remove existing rules if present (to avoid duplicates)
sudo iptables -D DOCKER-USER -i br+ -o ${LAN_INTERFACE} -j ACCEPT 2>/dev/null || true
sudo iptables -D DOCKER-USER -i ${LAN_INTERFACE} -o br+ -j ACCEPT 2>/dev/null || true

# Add rules to DOCKER-USER chain (runs before Docker's own rules)
# Allow forwarding FROM Docker bridge TO LAN interface
sudo iptables -I DOCKER-USER -i br+ -o ${LAN_INTERFACE} -j ACCEPT
echo -e "${GREEN}  ✓ Added rule: Docker bridge → ${LAN_INTERFACE}${NC}"

# Allow forwarding FROM LAN interface TO Docker bridge (return traffic)
sudo iptables -I DOCKER-USER -i ${LAN_INTERFACE} -o br+ -j ACCEPT
echo -e "${GREEN}  ✓ Added rule: ${LAN_INTERFACE} → Docker bridge${NC}"

echo ""
echo -e "${GREEN}Step 2/3: Verifying rules...${NC}"
echo ""
sudo iptables -L DOCKER-USER -v -n --line-numbers
echo ""

echo -e "${GREEN}Step 3/3: Making rules persistent...${NC}"

# Install iptables-persistent if not already installed
if ! dpkg -l | grep -q iptables-persistent; then
    echo -e "${YELLOW}Installing iptables-persistent to save rules across reboots...${NC}"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
fi

# Save current iptables rules
sudo netfilter-persistent save
echo -e "${GREEN}  ✓ Rules saved to /etc/iptables/rules.v4${NC}"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ WireGuard Routing Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Active forwarding rules:${NC}"
sudo iptables -L DOCKER-USER -v -n
echo ""
echo -e "${GREEN}Your VPN clients should now be able to access the local network!${NC}"
echo ""
echo -e "${YELLOW}Testing recommendations:${NC}"
echo "  1. From a VPN-connected device, try: ping 192.168.1.1"
echo "  2. Try accessing a local service: curl http://192.168.1.101"
echo "  3. Run WireGuard test script: ./scripts/test-wireguard-routing.sh"
echo ""
echo -e "${YELLOW}To verify rules persist after reboot:${NC}"
echo "  sudo reboot"
echo "  sudo iptables -L DOCKER-USER -v -n"
echo ""
