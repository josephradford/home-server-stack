#!/bin/bash
# setup-traefik-password.sh
# Generates htpasswd hash for Traefik dashboard and adds to .env
#
# This script takes the TRAEFIK_PASSWORD from .env and generates
# a hashed password that Traefik can use for basic authentication.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Traefik Dashboard Password Setup"
echo "================================="
echo ""

# Load environment variables (support both .env and .env.local)
ENV_FILE="${ENV_FILE:-.env}"

# Check if env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: $ENV_FILE file not found!${NC}"
    echo "Please run: cp .env.example .env"
    echo "Then edit .env with your TRAEFIK_PASSWORD"
    exit 1
fi

echo "Using environment file: $ENV_FILE"

# Load environment variables
set -a
source "$ENV_FILE"
set +a

# Check if TRAEFIK_PASSWORD is set
if [ -z "$TRAEFIK_PASSWORD" ]; then
    echo -e "${RED}ERROR: TRAEFIK_PASSWORD not set in $ENV_FILE file${NC}"
    echo ""
    echo "Please add to $ENV_FILE:"
    echo "  TRAEFIK_PASSWORD=your_secure_password"
    exit 1
fi

# Check if htpasswd is available
if ! command -v htpasswd &> /dev/null; then
    echo -e "${YELLOW}Installing apache2-utils (provides htpasswd)...${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y apache2-utils
fi

# Generate htpasswd hash
echo "Generating password hash..."
HASHED_PASSWORD=$(htpasswd -nbB admin "$TRAEFIK_PASSWORD" | sed -e 's/\$/\$\$/g')

# Check if TRAEFIK_DASHBOARD_USERS already exists in env file
if grep -q "^TRAEFIK_DASHBOARD_USERS=" "$ENV_FILE"; then
    echo "Updating existing TRAEFIK_DASHBOARD_USERS in $ENV_FILE..."
    # Use a temporary file to avoid sed issues with special characters
    grep -v "^TRAEFIK_DASHBOARD_USERS=" "$ENV_FILE" > "$ENV_FILE.tmp"
    echo "TRAEFIK_DASHBOARD_USERS=$HASHED_PASSWORD" >> "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
else
    echo "Adding TRAEFIK_DASHBOARD_USERS to $ENV_FILE..."
    echo "" >> "$ENV_FILE"
    echo "# Traefik Dashboard Basic Auth (generated from TRAEFIK_PASSWORD)" >> "$ENV_FILE"
    echo "# Do not edit manually - run ./scripts/setup-traefik-password.sh to regenerate" >> "$ENV_FILE"
    echo "TRAEFIK_DASHBOARD_USERS=$HASHED_PASSWORD" >> "$ENV_FILE"
fi

echo ""
echo -e "${GREEN}✓${NC} Traefik dashboard password configured!"
echo ""
echo "Credentials:"
echo "  Username: admin"
echo "  Password: (from TRAEFIK_PASSWORD in .env)"
echo ""
echo "Access dashboard at: https://traefik.\${DOMAIN}"
echo ""
echo "Note: Restart Traefik to apply changes:"
echo "  docker compose stop traefik"
echo "  docker compose rm -f traefik"
echo "  docker compose up -d traefik"
echo ""
