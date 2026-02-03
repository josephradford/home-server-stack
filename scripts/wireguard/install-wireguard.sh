#!/bin/bash
set -e

# Install WireGuard as System Service
# This script installs WireGuard directly on the host system (not Docker)
# This ensures VPN access remains available during Docker restarts

echo "🔒 WireGuard System Installation"
echo "================================="
echo ""

# Check if running as root or with sudo
if [ "$(id -u)" != "0" ]; then
    echo "❌ Error: This script must be run as root or with sudo"
    echo "   Run: sudo ./scripts/install-wireguard.sh"
    exit 1
fi

# Function to check if WireGuard is installed
check_wireguard_installation() {
    if command -v wg &> /dev/null; then
        echo "✓ WireGuard already installed"
        wg --version
        return 0
    else
        echo "ℹ️  WireGuard not found on system"
        return 1
    fi
}

# Check current WireGuard installation
echo "Checking current WireGuard installation..."
echo ""

if check_wireguard_installation; then
    echo ""
    echo "Checking WireGuard service status..."
    if systemctl is-active --quiet wg-quick@wg0; then
        echo "✓ WireGuard service (wg-quick@wg0) is running"
        systemctl status wg-quick@wg0 --no-pager | head -n 3
    elif systemctl is-enabled --quiet wg-quick@wg0 2>/dev/null; then
        echo "⚠️  WireGuard service (wg-quick@wg0) is enabled but not running"
        echo "   Start it with: sudo systemctl start wg-quick@wg0"
    else
        echo "ℹ️  WireGuard is installed but wg-quick@wg0 service not configured"
        echo "   Configure /etc/wireguard/wg0.conf then enable the service"
    fi
    echo ""
    echo "✅ WireGuard is already installed"
    echo ""
    echo "To reinstall, first run:"
    echo "  sudo apt-get remove --purge wireguard wireguard-tools"
    echo ""
    exit 0
fi

echo ""
echo "Installing WireGuard..."
echo ""

# Step 1: Update package lists
echo "Step 1/4: Updating package lists..."
echo "───────────────────────────────"
apt-get update
echo "✓ Package lists updated"
echo ""

# Step 2: Install WireGuard
echo "Step 2/4: Installing WireGuard packages..."
echo "───────────────────────────────"
echo "  • wireguard: Kernel module and core tools"
echo "  • wireguard-tools: wg and wg-quick utilities"
echo ""
apt-get install -y wireguard wireguard-tools
echo "✓ WireGuard packages installed"
echo ""

# Step 3: Enable IP forwarding
echo "Step 3/4: Enabling IP forwarding..."
echo "───────────────────────────────"
echo "  • Required for WireGuard to route traffic between peers"
echo "  • Persists across reboots via /etc/sysctl.conf"
if grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "  • IP forwarding already enabled in /etc/sysctl.conf"
else
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    echo "  • Added net.ipv4.ip_forward=1 to /etc/sysctl.conf"
fi
sysctl -w net.ipv4.ip_forward=1 > /dev/null
echo "✓ IP forwarding enabled"
echo ""

# Step 4: Create WireGuard directory with proper permissions
echo "Step 4/4: Creating WireGuard configuration directory..."
echo "───────────────────────────────"
echo "  • Directory: /etc/wireguard/"
echo "  • Permissions: 700 (root only)"
mkdir -p /etc/wireguard
chmod 700 /etc/wireguard
echo "✓ WireGuard directory created"
echo ""

# Verify installation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ WireGuard installed successfully!"
echo ""
wg --version
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Create WireGuard server configuration:"
echo "   sudo ./scripts/setup-wireguard-server.sh"
echo ""
echo "2. Enable and start WireGuard service:"
echo "   sudo systemctl enable wg-quick@wg0"
echo "   sudo systemctl start wg-quick@wg0"
echo ""
echo "3. Add VPN peers (clients):"
echo "   sudo ./scripts/wireguard-add-peer.sh <peer-name>"
echo ""
echo "4. Check WireGuard status:"
echo "   sudo wg show"
echo "   sudo systemctl status wg-quick@wg0"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
