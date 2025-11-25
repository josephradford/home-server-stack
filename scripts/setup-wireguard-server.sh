#!/bin/bash
set -e

# Setup WireGuard Server Configuration
# This script generates server keys and creates the initial WireGuard configuration

echo "🔒 WireGuard Server Setup"
echo "=========================="
echo ""

# Check if running as root
if [ "$(id -u)" != "0" ]; then
    echo "❌ Error: This script must be run as root or with sudo"
    echo "   Run: sudo ./scripts/setup-wireguard-server.sh"
    exit 1
fi

# Load environment variables
ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE file not found"
    exit 1
fi

echo "Using environment file: $ENV_FILE"
source "$ENV_FILE"

# Validate required variables
REQUIRED_VARS=("SERVER_IP" "WIREGUARD_PORT" "WIREGUARD_SUBNET")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: $var not set in $ENV_FILE"
        exit 1
    fi
done

echo ""
echo "Configuration:"
echo "  • Server IP: $SERVER_IP"
echo "  • VPN Port: $WIREGUARD_PORT"
echo "  • VPN Subnet: $WIREGUARD_SUBNET"
echo ""

# Check if wg0.conf already exists
WG_CONF="/etc/wireguard/wg0.conf"
if [ -f "$WG_CONF" ]; then
    echo "⚠️  $WG_CONF already exists"
    echo ""
    read -p "Do you want to regenerate keys and overwrite the configuration? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled"
        exit 0
    fi
    echo ""
    echo "Creating backup: $WG_CONF.backup"
    cp "$WG_CONF" "$WG_CONF.backup"
fi

# Generate server keys
echo "Generating WireGuard server keys..."
SERVER_PRIVATE_KEY=$(wg genkey)
SERVER_PUBLIC_KEY=$(echo "$SERVER_PRIVATE_KEY" | wg pubkey)
echo "✓ Keys generated"
echo ""

# Extract server IP from subnet (e.g., 10.13.13.1 from 10.13.13.0/24)
WIREGUARD_SERVER_IP=$(echo "$WIREGUARD_SUBNET" | sed 's|/.*||' | sed 's/\.0$/\.1/')

# Create wg0.conf
echo "Creating $WG_CONF..."
cat > "$WG_CONF" << WGEOF
[Interface]
# WireGuard Server Configuration
# Generated: $(date)
Address = $WIREGUARD_SERVER_IP/24
ListenPort = $WIREGUARD_PORT
PrivateKey = $SERVER_PRIVATE_KEY

# Forward traffic between peers
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# Peers will be added below using wireguard-add-peer.sh
WGEOF

chmod 600 "$WG_CONF"
echo "✓ Configuration created with permissions 600"
echo ""

# Display key information
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ WireGuard server configuration created!"
echo ""
echo "Server Details:"
echo "  • Config file: $WG_CONF"
echo "  • Server IP: $WIREGUARD_SERVER_IP"
echo "  • Listen port: $WIREGUARD_PORT"
echo "  • Public key: $SERVER_PUBLIC_KEY"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Enable and start WireGuard service:"
echo "   sudo systemctl enable wg-quick@wg0"
echo "   sudo systemctl start wg-quick@wg0"
echo ""
echo "2. Verify WireGuard is running:"
echo "   sudo wg show"
echo ""
echo "3. Add your first peer (client):"
echo "   sudo ./scripts/wireguard-add-peer.sh <peer-name>"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
