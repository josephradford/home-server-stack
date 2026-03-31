#!/bin/bash
# WireGuard Peer Management Script
# Manages WireGuard VPN peers for the home server stack
# WireGuard runs as a system service (wg-quick@wg0), NOT as a Docker container

set -e

WIREGUARD_CONFIG_DIR="./data/wireguard"
WG_CONF="/etc/wireguard/wg0.conf"
ACTION="${1:-list}"
PEER_NAME="$2"

function list_peers() {
    echo "📋 Current WireGuard Peers:"
    sudo wg show all
    echo ""
    echo "📁 Peer Configuration Files:"
    ls -lh "$WIREGUARD_CONFIG_DIR/peers/"* 2>/dev/null || echo "No peer configs found"
}

function show_peer_qr() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 qr <peer_name>"
        exit 1
    fi

    PEER_CONF="$WIREGUARD_CONFIG_DIR/peers/$PEER_NAME/$PEER_NAME.conf"
    if [ ! -f "$PEER_CONF" ]; then
        echo "❌ Peer config not found: $PEER_CONF"
        exit 1
    fi

    echo "📱 QR Code for peer: $PEER_NAME"
    if command -v qrencode &> /dev/null; then
        qrencode -t ansiutf8 < "$PEER_CONF"
    else
        echo "⚠️  qrencode not installed. Install with: sudo apt-get install qrencode"
        echo ""
        echo "Peer config:"
        cat "$PEER_CONF"
    fi
}

function add_peer() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 add <peer_name>"
        exit 1
    fi

    echo "➕ Adding new peer: $PEER_NAME"
    echo "   Use the dedicated script for adding peers:"
    echo "   sudo ./scripts/wireguard/wireguard-add-peer.sh $PEER_NAME"
}

function remove_peer() {
    if [ -z "$PEER_NAME" ]; then
        echo "❌ Error: Peer name required"
        echo "Usage: $0 remove <peer_name>"
        exit 1
    fi

    PEER_CONF="$WIREGUARD_CONFIG_DIR/peers/$PEER_NAME/$PEER_NAME.conf"
    if [ ! -f "$PEER_CONF" ]; then
        echo "❌ Peer config not found: $PEER_CONF"
        exit 1
    fi

    echo "🗑️  Removing peer: $PEER_NAME"
    echo "⚠️  WARNING: This will disconnect the peer immediately!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Get peer public key before deleting config
    PEER_PUBKEY=$(grep "^PublicKey" "$WG_CONF" | grep -A1 "# $PEER_NAME" | tail -1 | cut -d'=' -f2- | xargs || true)

    # Remove live from running interface if present
    if [ -n "$PEER_PUBKEY" ] && sudo wg show wg0 peers | grep -q "$PEER_PUBKEY"; then
        sudo wg set wg0 peer "$PEER_PUBKEY" remove
        echo "   Peer removed from live interface"
    fi

    # Remove peer section from wg0.conf
    sudo sed -i "/# $PEER_NAME/,/^$/d" "$WG_CONF"

    # Remove peer config files
    rm -rf "$WIREGUARD_CONFIG_DIR/peers/$PEER_NAME"

    echo "✅ Peer $PEER_NAME removed."
    echo "   Restart WireGuard to ensure clean state: sudo systemctl restart wg-quick@wg0"
}

function rotate_keys() {
    echo "🔑 WireGuard Key Rotation"
    echo "⚠️  WARNING: This will regenerate ALL peer keys!"
    echo "⚠️  All clients must reconfigure with new keys!"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Backup current config
    BACKUP_DIR="./backups/wireguard-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    sudo cp "$WG_CONF" "$BACKUP_DIR/wg0.conf"
    cp -r "$WIREGUARD_CONFIG_DIR/peers" "$BACKUP_DIR/" 2>/dev/null || true

    echo "💾 Backup created: $BACKUP_DIR"
    echo ""
    echo "🔄 To rotate keys, re-run setup and re-add each peer:"
    echo "   sudo ./scripts/wireguard/setup-wireguard-server.sh"
    for peer_dir in "$WIREGUARD_CONFIG_DIR/peers"/*/; do
        peer=$(basename "$peer_dir")
        echo "   sudo ./scripts/wireguard/wireguard-add-peer.sh $peer"
    done
    echo ""
    echo "Then restart: sudo systemctl restart wg-quick@wg0"
}

function check_security() {
    echo "🔒 WireGuard Security Check"
    echo ""

    # Check if 0.0.0.0/0 is configured in any peer client config (full tunneling)
    FULL_TUNNEL=false
    for conf in "$WIREGUARD_CONFIG_DIR/peers/"*/*.conf; do
        [ -f "$conf" ] || continue
        if grep -q "0.0.0.0/0" "$conf"; then
            echo "⚠️  WARNING: Full tunneling (0.0.0.0/0) detected in $(basename "$conf")!"
            echo "   This routes ALL client traffic through VPN"
            echo "   Recommendation: Use split tunneling (192.168.1.0/24,10.13.13.0/24)"
            FULL_TUNNEL=true
        fi
    done
    if [ "$FULL_TUNNEL" = false ]; then
        echo "✅ Split tunneling configured (no full tunnel routes in peer configs)"
    fi

    # Check peer count
    PEER_COUNT=$(sudo wg show wg0 peers 2>/dev/null | wc -l)
    echo "📊 Active peers: $PEER_COUNT"

    # Check port is listening
    if ss -tuln | grep -q ":51820"; then
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

    # Check systemd service
    if systemctl is-enabled --quiet wg-quick@wg0; then
        echo "✅ wg-quick@wg0 enabled (starts on boot)"
    else
        echo "⚠️  wg-quick@wg0 not enabled — won't start on boot"
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
        echo "  add <peer_name>   Add a new peer (delegates to wireguard-add-peer.sh)"
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
