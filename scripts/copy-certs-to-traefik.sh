#!/bin/bash
# copy-certs-to-traefik.sh
# Copies Let's Encrypt certificates to Traefik's certificate directory
#
# This script copies the certbot-generated certificates to a location
# where Traefik can read them and formats them correctly for Traefik's file provider.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Copying Let's Encrypt Certificates to Traefik"
echo "=============================================="
echo ""

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo -e "${RED}ERROR: .env file not found!${NC}"
    exit 1
fi

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}ERROR: DOMAIN not set in .env file${NC}"
    exit 1
fi

CERT_SOURCE="/etc/letsencrypt/live/$DOMAIN"
CERT_DEST="./data/traefik/certs"

# Check if source certificates exist
if ! sudo test -d "$CERT_SOURCE"; then
    echo -e "${RED}ERROR: Certificates not found at $CERT_SOURCE${NC}"
    echo "Please run ./scripts/setup-certbot-gandi.sh first"
    exit 1
fi

# Create destination directory
mkdir -p "$CERT_DEST"

# Copy certificates
echo "Copying certificates..."
echo "  From: $CERT_SOURCE"
echo "  To: $CERT_DEST"
echo ""

sudo cp "$CERT_SOURCE/fullchain.pem" "$CERT_DEST/$DOMAIN.crt"
sudo cp "$CERT_SOURCE/privkey.pem" "$CERT_DEST/$DOMAIN.key"

# Set appropriate permissions
sudo chown $(whoami):$(whoami) "$CERT_DEST/$DOMAIN.crt"
sudo chown $(whoami):$(whoami) "$CERT_DEST/$DOMAIN.key"
chmod 644 "$CERT_DEST/$DOMAIN.crt"
chmod 600 "$CERT_DEST/$DOMAIN.key"

echo -e "${GREEN}✓${NC} Certificates copied successfully!"
echo ""
echo "Certificate files:"
echo "  - Certificate: $CERT_DEST/$DOMAIN.crt"
echo "  - Private Key: $CERT_DEST/$DOMAIN.key"
echo ""
echo "Next: Run ./scripts/configure-traefik-file-provider.sh"
