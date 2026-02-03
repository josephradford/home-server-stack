#!/bin/bash
# setup-cert-renewal.sh
# Sets up automatic certificate renewal and Traefik reload
#
# This script creates a post-renewal hook that automatically copies
# renewed certificates to Traefik and reloads the container.

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Setting Up Automatic Certificate Renewal"
echo "========================================="
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

RENEWAL_HOOK_DIR="/etc/letsencrypt/renewal-hooks/deploy"
HOOK_SCRIPT="$RENEWAL_HOOK_DIR/traefik-reload.sh"
HOME_SERVER_DIR="$(pwd)"

# Create renewal hook directory
echo "Creating renewal hook directory..."
sudo mkdir -p "$RENEWAL_HOOK_DIR"

# Create post-renewal hook script
echo "Creating post-renewal hook script..."
sudo bash -c "cat > $HOOK_SCRIPT" <<EOF
#!/bin/bash
# traefik-reload.sh
# Post-renewal hook for certbot
# Automatically copies renewed certificates to Traefik and reloads the container
#
# This script is automatically run by certbot after successful certificate renewal.

set -e

DOMAIN="$DOMAIN"
HOME_SERVER_DIR="$HOME_SERVER_DIR"
CERT_SOURCE="/etc/letsencrypt/live/\$DOMAIN"
CERT_DEST="\$HOME_SERVER_DIR/data/traefik/certs"

echo "[\$(date)] Certificate renewed for \$DOMAIN" >> /var/log/certbot-traefik-reload.log

# Copy certificates
echo "[\$(date)] Copying certificates to Traefik..." >> /var/log/certbot-traefik-reload.log
cp "\$CERT_SOURCE/fullchain.pem" "\$CERT_DEST/\$DOMAIN.crt"
cp "\$CERT_SOURCE/privkey.pem" "\$CERT_DEST/\$DOMAIN.key"

# Set permissions
chown $(whoami):$(whoami) "\$CERT_DEST/\$DOMAIN.crt"
chown $(whoami):$(whoami) "\$CERT_DEST/\$DOMAIN.key"
chmod 644 "\$CERT_DEST/\$DOMAIN.crt"
chmod 600 "\$CERT_DEST/\$DOMAIN.key"

# Reload Traefik (restart to pick up new certificates)
echo "[\$(date)] Reloading Traefik container..." >> /var/log/certbot-traefik-reload.log
cd "\$HOME_SERVER_DIR"
docker compose restart traefik >> /var/log/certbot-traefik-reload.log 2>&1

echo "[\$(date)] Certificate renewal and Traefik reload complete!" >> /var/log/certbot-traefik-reload.log
EOF

# Make hook script executable
sudo chmod +x "$HOOK_SCRIPT"

echo -e "${GREEN}✓${NC} Renewal hook created: $HOOK_SCRIPT"
echo ""

# Create log file
sudo touch /var/log/certbot-traefik-reload.log
sudo chmod 644 /var/log/certbot-traefik-reload.log

echo -e "${GREEN}✓${NC} Log file created: /var/log/certbot-traefik-reload.log"
echo ""

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Automatic renewal is now configured!"
echo ""
echo "How it works:"
echo "  - Certbot's snap automatically runs 'certbot renew' twice daily"
echo "  - When certificates are renewed (30 days before expiry), the hook script:"
echo "    1. Copies new certificates to Traefik directory"
echo "    2. Restarts Traefik container to load new certificates"
echo "    3. Logs everything to /var/log/certbot-traefik-reload.log"
echo ""
echo "Your certificate is valid for 90 days and will auto-renew at 60 days."
echo ""
echo -e "${YELLOW}Testing renewal:${NC}"
echo "  - Wait 2-4 hours for DNS caches to clear, then test with:"
echo "    sudo certbot renew --dry-run"
echo "  - Force renewal (if needed): sudo certbot renew --force-renewal"
echo ""
echo "View logs:"
echo "  - Renewal logs: sudo tail -f /var/log/certbot-traefik-reload.log"
echo "  - Certbot logs: sudo journalctl -u snap.certbot.renew.service -f"
echo ""
