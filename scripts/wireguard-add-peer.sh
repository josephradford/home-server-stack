#!/bin/bash
set -e

# Add WireGuard Peer (Client)
# This script generates a peer configuration and adds it to the WireGuard server

echo "🔑 WireGuard Add Peer"
echo "===================="
echo ""

# Check if running as root
if [ "$(id -u)" != "0" ]; then
    echo "❌ Error: This script must be run as root or with sudo"
    echo "   Run: sudo ./scripts/wireguard-add-peer.sh <peer-name>"
    exit 1
fi

# Get peer name from argument
PEER_NAME="${1:-}"
if [ -z "$PEER_NAME" ]; then
    echo "❌ Error: Peer name required"
    echo "Usage: sudo ./scripts/wireguard-add-peer.sh <peer-name>"
    echo "Example: sudo ./scripts/wireguard-add-peer.sh laptop"
    exit 1
fi

# Validate peer name (alphanumeric and hyphens only)
if ! [[ "$PEER_NAME" =~ ^[a-zA-Z0-9-]+$ ]]; then
    echo "❌ Error: Invalid peer name. Use only alphanumeric and hyphens"
    exit 1
fi

# Load environment variables
ENV_FILE="${ENV_FILE:-.env}"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE file not found"
    exit 1
fi

source "$ENV_FILE"

# Validate required variables
if [ -z "$SERVER_IP" ] || [ -z "$WIREGUARD_PORT" ] || [ -z "$WIREGUARD_SUBNET" ]; then
    echo "❌ Error: Required variables missing in $ENV_FILE"
    echo "   Required: SERVER_IP, WIREGUARD_PORT, WIREGUARD_SUBNET"
    exit 1
fi

WG_CONF="/etc/wireguard/wg0.conf"
PEERS_DIR="data/wireguard/peers"

# Check if WireGuard is configured
if [ ! -f "$WG_CONF" ]; then
    echo "❌ Error: WireGuard not configured"
    echo "Run: sudo ./scripts/setup-wireguard-server.sh"
    exit 1
fi

# Create peers directory if it doesn't exist
mkdir -p "$PEERS_DIR"

# Check if peer already exists
if grep -q "Name = $PEER_NAME" "$WG_CONF" 2>/dev/null; then
    echo "❌ Error: Peer '$PEER_NAME' already exists in $WG_CONF"
    exit 1
fi

if [ -f "$PEERS_DIR/$PEER_NAME.conf" ]; then
    echo "❌ Error: Peer configuration already exists at $PEERS_DIR/$PEER_NAME.conf"
    exit 1
fi

echo "Adding peer: $PEER_NAME"
echo ""

# Generate peer keys
echo "Generating peer keys..."
PEER_PRIVATE_KEY=$(wg genkey)
PEER_PUBLIC_KEY=$(echo "$PEER_PRIVATE_KEY" | wg pubkey)
echo "✓ Keys generated"
echo ""

# Find next available IP in subnet
# Extract base subnet (e.g., 10.13.13 from 10.13.13.0/24)
SUBNET_BASE=$(echo "$WIREGUARD_SUBNET" | sed 's/\.0\/24$//')
LAST_OCTET=2  # Start from .2 (server is .1)

# Check existing peers for highest IP
if [ -f "$WG_CONF" ]; then
    EXISTING_IPS=$(grep -oP "Address = $SUBNET_BASE\.\K[0-9]+" "$WG_CONF" 2>/dev/null || true)
    if [ ! -z "$EXISTING_IPS" ]; then
        LAST_OCTET=$(($(echo "$EXISTING_IPS" | sort -rn | head -1) + 1))
    fi
fi

PEER_IP="$SUBNET_BASE.$LAST_OCTET"

# Add peer to server config
echo "Adding peer to $WG_CONF..."
cat >> "$WG_CONF" << PEEREOF

# Peer: $PEER_NAME
[Peer]
PublicKey = $PEER_PUBLIC_KEY
AllowedIPs = $PEER_IP/32
PEEREOF

echo "✓ Peer added to server configuration"
echo ""

# Create peer client config
echo "Creating peer client configuration..."
mkdir -p "$PEERS_DIR"
cat > "$PEERS_DIR/$PEER_NAME.conf" << CLIENTEOF
[Interface]
Address = $PEER_IP/24
PrivateKey = $PEER_PRIVATE_KEY
DNS = $(echo $SERVER_IP | sed 's/[0-9]*$/53/'), 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = $(grep "PrivateKey = " "$WG_CONF" | head -1 | sed 's/.*PrivateKey = //' | wg pubkey)
AllowedIPs = 192.168.1.0/24, 10.13.13.0/24
Endpoint = $SERVER_IP:$WIREGUARD_PORT
PersistentKeepalive = 25
CLIENTEOF

chmod 600 "$PEERS_DIR/$PEER_NAME.conf"
echo "✓ Client configuration created"
echo ""

# Reload WireGuard if it's running
if systemctl is-active --quiet wg-quick@wg0; then
    echo "Reloading WireGuard service..."
    systemctl restart wg-quick@wg0
    echo "✓ WireGuard reloaded"
    echo ""
fi

# Display connection info
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Peer '$PEER_NAME' added successfully!"
echo ""
echo "Peer Details:"
echo "  • Name: $PEER_NAME"
echo "  • VPN IP: $PEER_IP"
echo "  • Config file: $PEERS_DIR/$PEER_NAME.conf"
echo ""
echo "To use this peer:"
echo "  1. Copy the configuration file to your device:"
echo "     $PEERS_DIR/$PEER_NAME.conf"
echo ""
echo "  2. Import into WireGuard app on your device"
echo ""
echo "  3. Test connection:"
echo "     ping $PEER_IP"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
