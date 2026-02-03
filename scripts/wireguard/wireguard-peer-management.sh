#!/bin/bash
# WireGuard Peer Management Script
# Manages WireGuard VPN peers for the home server stack

set -e

WIREGUARD_CONFIG_DIR="./data/wireguard"
ACTION="${1:-list}"
PEER_NAME="$2"

function list_peers() {
    echo "📋 Current WireGuard Peers:"
    docker exec wireguard wg show all
    echo ""
    echo "📁 Peer Configuration Files:"
    ls -lh "$WIREGUARD_CONFIG_DIR/peer_"* 2>/dev/null || echo "No peer configs found"
}

function show_peer_qr() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 qr <peer_name>"
        exit 1
    fi

    echo "📱 QR Code for peer: $PEER_NAME"
    docker exec wireguard /app/show-peer "$PEER_NAME"
}

function add_peer() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 add <peer_name>"
        exit 1
    fi

    echo "➕ Adding new peer: $PEER_NAME"

    # Regenerate config with new peer count
    CURRENT_PEERS=$(docker exec wireguard wg show wg0 peers | wc -l)
    NEW_PEER_COUNT=$((CURRENT_PEERS + 1))

    docker stop wireguard
    docker rm wireguard

    # Update PEERS environment variable and restart
    echo "🔄 Restarting WireGuard with $NEW_PEER_COUNT peers..."
    # User should update .env and restart manually
    echo "⚠️  Update WIREGUARD_PEERS=$NEW_PEER_COUNT in .env and run:"
    echo "   docker compose up -d wireguard"
}

function remove_peer() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 remove <peer_name>"
        exit 1
    fi

    echo "🗑️  Removing peer: $PEER_NAME"
    echo "⚠️  WARNING: This will disconnect the peer immediately!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Remove peer configuration
    rm -f "$WIREGUARD_CONFIG_DIR/peer_$PEER_NAME"*

    echo "✅ Peer $PEER_NAME removed. Restart WireGuard to apply:"
    echo "   docker compose restart wireguard"
}

function rotate_keys() {
    echo "🔑 WireGuard Key Rotation"
    echo "⚠️  WARNING: This will regenerate ALL peer keys and QR codes!"
    echo "⚠️  All clients must reconfigure with new keys!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Backup current config
    BACKUP_DIR="./backups/wireguard-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp -r "$WIREGUARD_CONFIG_DIR"/* "$BACKUP_DIR/"

    echo "💾 Backup created: $BACKUP_DIR"

    # Remove and recreate WireGuard
    docker stop wireguard
    docker rm wireguard
    rm -rf "$WIREGUARD_CONFIG_DIR"/*

    echo "🔄 Recreating WireGuard with new keys..."
    docker compose up -d wireguard

    echo "✅ Key rotation complete!"
    echo "📋 New peer configurations available in: $WIREGUARD_CONFIG_DIR"
}

function check_security() {
    echo "🔒 WireGuard Security Check"
    echo ""

    # Check if 0.0.0.0/0 is configured (bad)
    if docker exec wireguard cat /config/wg0.conf | grep -q "0.0.0.0/0"; then
        echo "⚠️  WARNING: Full tunneling (0.0.0.0/0) detected!"
        echo "   This routes ALL client traffic through VPN"
        echo "   Recommendation: Use split tunneling (192.168.1.0/24,10.13.13.0/24)"
    else
        echo "✅ Split tunneling configured"
    fi

    # Check peer count
    PEER_COUNT=$(docker exec wireguard wg show wg0 peers | wc -l)
    echo "📊 Active peers: $PEER_COUNT"

    # Check port exposure
    if netstat -tuln | grep -q ":51820"; then
        echo "✅ WireGuard port 51820/udp is listening"
    else
        echo "❌ WireGuard port not listening!"
    fi

    # Check firewall
    if command -v ufw &> /dev/null; then
        if sudo ufw status | grep -q "51820/udp"; then
            echo "✅ UFW firewall rule configured"
        else
            echo "⚠️  No UFW rule for WireGuard port"
        fi
    fi

    echo ""
    echo "🔐 Security Recommendations:"
    echo "   - Rotate keys every 90 days"
    echo "   - Limit peer count to necessary devices"
    echo "   - Monitor connection logs regularly"
    echo "   - Use strong DNS filtering (AdGuard)"
}

case "$ACTION" in
    list)
        list_peers
        ;;
    qr)
        show_peer_qr
        ;;
    add)
        add_peer
        ;;
    remove)
        remove_peer
        ;;
    rotate)
        rotate_keys
        ;;
    check)
        check_security
        ;;
    *)
        echo "WireGuard Peer Management"
        echo ""
        echo "Usage: $0 <command> [peer_name]"
        echo ""
        echo "Commands:"
        echo "  list              List all peers and their status"
        echo "  qr <peer_name>    Show QR code for peer configuration"
        echo "  add <peer_name>   Add a new peer"
        echo "  remove <peer_name> Remove a peer"
        echo "  rotate            Rotate all peer keys (WARNING: disconnects all)"
        echo "  check             Run security checks"
        echo ""
        echo "Examples:"
        echo "  $0 list"
        echo "  $0 qr phone"
        echo "  $0 add laptop"
        echo "  $0 remove old-device"
        exit 1
        ;;
esac
