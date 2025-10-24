#!/bin/bash
set -e

# Setup User Permissions for Docker
# This script adds the current user to the docker group to allow running Docker commands without sudo
# This is a ONE-TIME setup that persists across reboots

echo "🔐 Setting Up User Permissions"
echo "==============================="
echo ""

# Get current user
CURRENT_USER=$(whoami)

# Check if running as root
if [ "$CURRENT_USER" = "root" ]; then
    echo "❌ Error: This script should not be run as root"
    echo "   Run as your regular user: ./scripts/setup-user-permissions.sh"
    exit 1
fi

# Check if user is already in docker group
if groups "$CURRENT_USER" | grep -q '\bdocker\b'; then
    echo "✓ User '$CURRENT_USER' is already in the docker group"
    echo ""

    # Check if current session has docker group active
    if groups | grep -q '\bdocker\b'; then
        echo "✓ Docker group is active in current session"
        echo ""
        echo "You can run docker commands without sudo!"
    else
        echo "⚠️  Docker group is not active in current session"
        echo ""
        echo "To activate without logging out, run:"
        echo "  newgrp docker"
        echo ""
        echo "Or simply logout and login again."
    fi

    exit 0
fi

echo "Adding user '$CURRENT_USER' to docker group..."
echo "This requires sudo privileges."
echo ""

# Add user to docker group
sudo usermod -aG docker "$CURRENT_USER"

echo ""
echo "✅ User '$CURRENT_USER' added to docker group successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  IMPORTANT: You must log out and log back in for this change to take effect"
echo ""
echo "Options to apply the change:"
echo ""
echo "1. Logout and login again (recommended):"
echo "   exit"
echo ""
echo "2. Apply in current session only (temporary until logout):"
echo "   newgrp docker"
echo ""
echo "After logging back in, you can run docker commands without sudo:"
echo "  docker ps"
echo "  make start"
echo "  make logs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
