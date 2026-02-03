#!/bin/bash
# Test WireGuard routing and connectivity
# Validates VPN configuration and security settings

set -e

echo "🧪 WireGuard Routing and Security Test"
echo ""

# Test 1: Check WireGuard interface
echo "1️⃣  Checking WireGuard interface..."
if docker exec wireguard wg show wg0 &> /dev/null; then
    echo "   ✅ wg0 interface is up"
else
    echo "   ❌ wg0 interface not found!"
    exit 1
fi

# Test 2: Check IP forwarding
echo "2️⃣  Checking IP forwarding..."
if docker exec wireguard sysctl net.ipv4.ip_forward | grep -q "= 1"; then
    echo "   ✅ IP forwarding enabled"
else
    echo "   ⚠️  IP forwarding disabled"
fi

# Test 3: Check allowed IPs configuration
echo "3️⃣  Checking AllowedIPs configuration..."
ALLOWED_IPS=$(docker exec wireguard cat /config/peer1/peer1.conf | grep AllowedIPs | cut -d'=' -f2 | xargs)
if [[ "$ALLOWED_IPS" == *"0.0.0.0/0"* ]]; then
    echo "   ⚠️  Full tunneling detected: $ALLOWED_IPS"
    echo "   Recommendation: Use split tunneling for better security"
else
    echo "   ✅ Split tunneling configured: $ALLOWED_IPS"
fi

# Test 4: Check DNS routing
echo "4️⃣  Checking DNS configuration..."
PEER_DNS=$(docker exec wireguard cat /config/peer1/peer1.conf | grep DNS | cut -d'=' -f2 | xargs)
echo "   DNS: $PEER_DNS"
if [ -n "$PEER_DNS" ]; then
    echo "   ✅ DNS routing configured (AdGuard)"
else
    echo "   ⚠️  No DNS configured"
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

# Test 6: Check peer connectivity
echo "6️⃣  Checking peer handshakes..."
PEER_COUNT=$(docker exec wireguard wg show wg0 peers | wc -l)
ACTIVE_PEERS=$(docker exec wireguard wg show wg0 latest-handshakes | awk '$2 > 0' | wc -l)
echo "   Total peers: $PEER_COUNT"
echo "   Active peers (with recent handshake): $ACTIVE_PEERS"

# Test 7: Check security settings
echo "7️⃣  Checking security settings..."
if docker inspect wireguard | grep -q "no-new-privileges"; then
    echo "   ✅ no-new-privileges enabled"
else
    echo "   ⚠️  no-new-privileges not set"
fi

# Test 8: Check healthcheck
echo "8️⃣  Checking container health..."
HEALTH=$(docker inspect wireguard --format='{{.State.Health.Status}}' 2>/dev/null || echo "no healthcheck")
if [ "$HEALTH" == "healthy" ]; then
    echo "   ✅ Container is healthy"
elif [ "$HEALTH" == "no healthcheck" ]; then
    echo "   ℹ️  No healthcheck configured"
else
    echo "   ⚠️  Container health: $HEALTH"
fi

echo ""
echo "✅ WireGuard routing test complete!"
echo ""
echo "Summary:"
echo "  - Interface: OK"
echo "  - Routing: $([ $(docker exec wireguard sysctl net.ipv4.ip_forward | grep -c '= 1') -eq 1 ] && echo 'OK' || echo 'WARNING')"
echo "  - Split Tunneling: $([ $(echo "$ALLOWED_IPS" | grep -c '0.0.0.0/0') -eq 0 ] && echo 'OK' || echo 'WARNING')"
echo "  - DNS: $([ -n "$PEER_DNS" ] && echo 'OK' || echo 'WARNING')"
echo "  - Active Peers: $ACTIVE_PEERS/$PEER_COUNT"
