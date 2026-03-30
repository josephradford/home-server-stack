#!/bin/bash
set -e

# Install Docker from Official Repository
# This script removes snap Docker and installs Docker CE from Docker's official repository
# This is a ONE-TIME setup for servers

echo "🐳 Docker Official Installation"
echo "================================"
echo ""

# Check if running as root
if [ "$(id -u)" = "0" ]; then
    echo "❌ Error: This script should not be run as root"
    echo "   Run as your regular user: ./scripts/install-docker-official.sh"
    exit 1
fi

# Function to check if Docker is installed and how
check_docker_installation() {
    if command -v docker &> /dev/null; then
        DOCKER_PATH=$(which docker)
        if [[ "$DOCKER_PATH" == *"snap"* ]]; then
            echo "📦 Snap Docker detected at: $DOCKER_PATH"
            return 1  # Snap version found
        else
            echo "✓ Docker CE already installed at: $DOCKER_PATH"
            docker --version
            return 0  # Official version found
        fi
    else
        echo "ℹ️  Docker not found on system"
        return 2  # Not installed
    fi
}

# Check current Docker installation
echo "Checking current Docker installation..."
echo ""

check_docker_installation || DOCKER_STATUS=$?

if [ $DOCKER_STATUS -eq 0 ]; then
    echo ""
    echo "✅ Docker CE is already installed from official repository"
    echo ""
    echo "If you want to reinstall, first run:"
    echo "  sudo apt-get remove docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
    echo ""
    exit 0
fi

# Warn about snap Docker removal
if [ $DOCKER_STATUS -eq 1 ]; then
    echo ""
    echo "⚠️  WARNING: This will remove snap Docker and reinstall from official repository"
    echo ""
    echo "What happens:"
    echo "  • Snap Docker will be removed (containers will stop)"
    echo "  • Official Docker CE will be installed"
    echo "  • Containers can be recreated after installation"
    echo "  • Your data in ./data/ directories will be preserved"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 0
    fi
    echo ""
fi

# Step 1: Remove snap Docker if present
if [ $DOCKER_STATUS -eq 1 ]; then
    echo "Step 1/8: Removing snap Docker..."
    echo "───────────────────────────────"
    sudo snap remove docker
    echo "✓ Snap Docker removed"
    echo ""
fi

# Step 2: Update package lists
echo "Step 2/8: Updating package lists..."
echo "───────────────────────────────"
sudo apt-get update
echo "✓ Package lists updated"
echo ""

# Step 3: Install prerequisites
echo "Step 3/8: Installing prerequisites (ca-certificates, curl)..."
echo "───────────────────────────────"
echo "  • ca-certificates: SSL/TLS certificate bundle for secure downloads"
echo "  • curl: Tool for downloading Docker's GPG key"
sudo apt-get install -y ca-certificates curl
echo "✓ Prerequisites installed"
echo ""

# Step 4: Create keyrings directory
echo "Step 4/8: Creating /etc/apt/keyrings directory..."
echo "───────────────────────────────"
echo "  • Modern location for storing GPG keys (Ubuntu 22.04+)"
echo "  • Permissions: rwxr-xr-x (755)"
sudo install -m 0755 -d /etc/apt/keyrings
echo "✓ Keyrings directory created"
echo ""

# Step 5: Download Docker's GPG key
echo "Step 5/8: Downloading Docker's GPG key..."
echo "───────────────────────────────"
echo "  • GPG key = cryptographic signature from Docker Inc."
echo "  • Used to verify packages actually come from Docker"
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "✓ Docker GPG key downloaded to /etc/apt/keyrings/docker.asc"
echo ""

# Step 6: Make GPG key readable
echo "Step 6/8: Setting GPG key permissions..."
echo "───────────────────────────────"
echo "  • Making key readable by all users (needed by apt)"
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "✓ GPG key permissions set"
echo ""

# Step 7: Add Docker repository
echo "Step 7/8: Adding Docker repository to apt..."
echo "───────────────────────────────"
ARCH=$(dpkg --print-architecture)
VERSION_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
echo "  • Architecture: $ARCH"
echo "  • Ubuntu version: $VERSION_CODENAME"
echo "  • Repository: https://download.docker.com/linux/ubuntu"

echo \
  "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $VERSION_CODENAME stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "✓ Docker repository added to /etc/apt/sources.list.d/docker.list"
echo ""

# Step 8: Update package lists again and install Docker
echo "Step 8/8: Installing Docker packages..."
echo "───────────────────────────────"
echo "  • docker-ce: Docker Community Edition engine"
echo "  • docker-ce-cli: Docker command-line interface"
echo "  • containerd.io: Container runtime"
echo "  • docker-buildx-plugin: Advanced build features"
echo "  • docker-compose-plugin: Docker Compose v2"
echo ""
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo "✓ Docker packages installed"
echo ""

# Verify installation
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Docker CE installed successfully!"
echo ""
docker --version
echo ""
echo "Docker daemon status:"
sudo systemctl status docker --no-pager | head -n 3
echo ""

# Check if docker group was created
if getent group docker > /dev/null 2>&1; then
    DOCKER_GID=$(getent group docker | cut -d: -f3)
    echo "✓ Docker group created with GID: $DOCKER_GID"
    echo "✓ Docker socket ownership: $(ls -l /var/run/docker.sock | awk '{print $3":"$4}')"
else
    echo "⚠️  Warning: Docker group not found (unexpected)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Add your user to the docker group:"
echo "   ./scripts/setup-user-permissions.sh"
echo ""
echo "2. Update PGID in your .env file:"
echo "   nano .env"
echo "   Change: PGID=1000"
echo "   To:     PGID=$DOCKER_GID"
echo ""
echo "3. Restart your containers:"
echo "   make start"
echo ""
echo "4. Recreate Homepage with correct PGID:"
echo "   docker compose -f docker-compose.dashboard.yml up -d --force-recreate homepage"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
