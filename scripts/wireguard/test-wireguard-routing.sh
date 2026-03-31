#!/bin/bash
# Test WireGuard routing and connectivity
# Validates VPN configuration and security settings
# WireGuard runs as a system service (not Docker)

set -e

echo "🧪 WireGuard Routing and Security Test"
echo ""

# Test 1: Check WireGuard interface
echo "1️⃣  Checking WireGuard interface..."
if ip link show wg0 &> /dev/null; then
    echo "   ✅ wg0 interface is up"
else
    echo "   ❌ wg0 interface not found!"
    echo "   Run: sudo systemctl start wg-quick@wg0"
    exit 1
fi

# Test 2: Check IP forwarding
echo "2️⃣  Checking IP forwarding..."
if sysctl net.ipv4.ip_forward | grep -q "= 1"; then
    echo "   ✅ IP forwarding enabled"
else
    echo "   ⚠️  IP forwarding disabled"
    echo "   Run: sudo sysctl -w net.ipv4.ip_forward=1"
fi

# Test 3: Check allowed IPs configuration (split tunneling)
echo "3️⃣  Checking AllowedIPs configuration..."
PEER_CONF=$(sudo grep -r "AllowedIPs" /etc/wireguard/wg0.conf 2>/dev/null || echo "")
if [[ "$PEER_CONF" == *"0.0.0.0/0"* ]]; then
    echo "   ⚠️  Full tunneling detected in server config"
    echo "   Recommendation: Use split tunneling for better security"
else
    echo "   ✅ Split tunneling configured (no full tunnel route in server config)"
fi

# Check peer client configs if available
PEER_DIR="./data/wireguard/peers"
if [ -d "$PEER_DIR" ]; then
    for conf in "$PEER_DIR"/*/*.conf 2>/dev/null; do
        [ -f "$conf" ] || continue
        ALLOWED=$(grep "AllowedIPs" "$conf" | cut -d'=' -f2 | xargs)
        PEER_NAME=$(basename "$(dirname "$conf")")
        if [[ "$ALLOWED" == *"0.0.0.0/0"* ]]; then
            echo "   ⚠️  Full tunneling in peer $PEER_NAME: $ALLOWED"
        else
            echo "   ✅ Split tunneling for peer $PEER_NAME: $ALLOWED"
        fi
    done
fi

# Test 4: Check DNS configuration in peer configs
echo "4️⃣  Checking DNS configuration in peer configs..."
if [ -d "$PEER_DIR" ]; then
    for conf in "$PEER_DIR"/*/*.conf 2>/dev/null; do
        [ -f "$conf" ] || continue
        PEER_DNS=$(grep "^DNS" "$conf" | cut -d'=' -f2 | xargs)
        PEER_NAME=$(basename "$(dirname "$conf")")
        if [ -n "$PEER_DNS" ]; then
            echo "   ✅ $PEER_NAME DNS: $PEER_DNS"
        else
            echo "   ⚠️  $PEER_NAME: No DNS configured"
        fi
    done
else
    echo "   ℹ️  No peer configs found at $PEER_DIR"
fi

# Test 5: Check firewall rules
echo "5️⃣  Checking firewall rules..."
if command -v ufw &> /dev/null; then
    if sudo ufw status | grep -q "51820/udp"; then
        echo "   ✅ UFW rule exists for WireGuard"
    else
        echo "   ⚠️  No UFW rule found. Add with: sudo ufw allow 51820/udp"
    fi
else
    echo "   ℹ️  UFW not installed (firewall check skipped)"
fi

# Test 6: Check DOCKER-USER iptables rules for VPN → Docker routing
echo "6️⃣  Checking DOCKER-USER iptables rules..."
if sudo iptables -L DOCKER-USER -n 2>/dev/null | grep -q "10.13.13.0/24"; then
    echo "   ✅ DOCKER-USER rules exist for VPN subnet"
else
    echo "   ⚠️  No DOCKER-USER rules for VPN subnet"
    echo "   Run: make wireguard-routing"
fi

# Test 7: Check peer handshakes
echo "7️⃣  Checking peer handshakes..."
PEER_COUNT=$(sudo wg show wg0 peers 2>/dev/null | wc -l)
ACTIVE_PEERS=$(sudo wg show wg0 latest-handshakes 2>/dev/null | awk '$2 > 0' | wc -l)
echo "   Total peers: $PEER_COUNT"
echo "   Active peers (with recent handshake): $ACTIVE_PEERS"

# Test 8: Check systemd service
echo "8️⃣  Checking systemd service..."
if systemctl is-active --quiet wg-quick@wg0; then
    echo "   ✅ wg-quick@wg0 is active"
else
    echo "   ❌ wg-quick@wg0 is not active"
fi
if systemctl is-enabled --quiet wg-quick@wg0; then
    echo "   ✅ wg-quick@wg0 is enabled (starts on boot)"
else
    echo "   ⚠️  wg-quick@wg0 is not enabled (won't start on boot)"
    echo "   Run: sudo systemctl enable wg-quick@wg0"
fi

echo ""
echo "✅ WireGuard routing test complete!"
echo ""
echo "Summary:"
echo "  - Interface: OK"
echo "  - IP Forwarding: $(sysctl -n net.ipv4.ip_forward | grep -q 1 && echo 'OK' || echo 'WARNING')"
echo "  - Active Peers: $ACTIVE_PEERS/$PEER_COUNT"
