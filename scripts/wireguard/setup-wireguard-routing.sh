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
    set -a
    source .env
    set +a
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

# Get Docker bridge network subnet (used for DOCKER-USER routing rules)
DOCKER_NETWORK=$(docker network inspect home-server-stack_homeserver -f '{{(index .IPAM.Config 0).Subnet}}' 2>/dev/null || echo "")
if [ -z "$DOCKER_NETWORK" ]; then
    echo -e "${YELLOW}Warning: Docker network not found. Will use default 172.18.0.0/16${NC}"
    echo -e "${YELLOW}Start the stack first (make start), then re-run this script for accurate detection.${NC}"
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
echo -e "${GREEN}Step 1/3: Adding iptables DOCKER-USER rules...${NC}"

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
echo -e "${GREEN}Step 2/3: Installing systemd service for boot persistence...${NC}"
echo ""
echo -e "${YELLOW}Note: iptables-persistent is NOT used here. Docker initialises its${NC}"
echo -e "${YELLOW}iptables chains at startup, which would overwrite any rules restored${NC}"
echo -e "${YELLOW}before Docker runs. Instead, a systemd service runs AFTER Docker and${NC}"
echo -e "${YELLOW}re-applies only these two rules.${NC}"
echo ""

# Write the rule-apply script
APPLY_SCRIPT="/usr/local/bin/wireguard-docker-routing.sh"
sudo tee "$APPLY_SCRIPT" > /dev/null << SCRIPTEOF
#!/bin/bash
# Applied by wireguard-docker-routing.service after Docker starts.
# Managed by setup-wireguard-routing.sh — do not edit manually.
set -e
LAN_INTERFACE=\$(ip route | grep default | awk '{print \$5}' | head -n1)
if [ -z "\$LAN_INTERFACE" ]; then
    echo "wireguard-docker-routing: could not detect LAN interface" >&2
    exit 1
fi
iptables -D DOCKER-USER -i br+ -o "\${LAN_INTERFACE}" -j ACCEPT 2>/dev/null || true
iptables -D DOCKER-USER -i "\${LAN_INTERFACE}" -o br+ -j ACCEPT 2>/dev/null || true
iptables -I DOCKER-USER -i br+ -o "\${LAN_INTERFACE}" -j ACCEPT
iptables -I DOCKER-USER -i "\${LAN_INTERFACE}" -o br+ -j ACCEPT
echo "wireguard-docker-routing: rules applied (LAN interface: \${LAN_INTERFACE})"
SCRIPTEOF
sudo chmod +x "$APPLY_SCRIPT"
echo -e "${GREEN}  ✓ Installed ${APPLY_SCRIPT}${NC}"

# Write the systemd unit
UNIT_FILE="/etc/systemd/system/wireguard-docker-routing.service"
sudo tee "$UNIT_FILE" > /dev/null << UNITEOF
[Unit]
Description=WireGuard Docker bridge routing rules
# Must run after Docker has initialised its iptables chains
After=docker.service wg-quick@wg0.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/wireguard-docker-routing.sh

[Install]
WantedBy=multi-user.target
UNITEOF
echo -e "${GREEN}  ✓ Installed ${UNIT_FILE}${NC}"

sudo systemctl daemon-reload
sudo systemctl enable wireguard-docker-routing.service
echo -e "${GREEN}  ✓ Service enabled (will start automatically on next boot)${NC}"

echo ""
echo -e "${GREEN}Step 3/3: Verifying rules...${NC}"
echo ""
sudo iptables -L DOCKER-USER -v -n --line-numbers
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ WireGuard Routing Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}Your VPN clients should now be able to access the local network!${NC}"
echo ""
echo -e "${YELLOW}Testing recommendations:${NC}"
echo "  1. From a VPN-connected device, try: ping 192.168.1.1"
echo "  2. Try accessing a local service: curl http://192.168.1.101"
echo "  3. Run WireGuard test: make wireguard-test"
echo ""
echo -e "${YELLOW}To verify rules persist after reboot:${NC}"
echo "  sudo reboot"
echo "  sudo iptables -L DOCKER-USER -v -n"
echo ""
