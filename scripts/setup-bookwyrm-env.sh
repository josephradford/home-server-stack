#!/bin/bash
# Setup Bookwyrm .env file with values from parent environment
# This script is called by make bookwyrm-setup

set -e

BOOKWYRM_DIR="external/bookwyrm-docker"
PARENT_ENV=".env"
BOOKWYRM_ENV="${BOOKWYRM_DIR}/.env"

echo "Configuring Bookwyrm environment..."

# Check that parent .env exists
if [ ! -f "$PARENT_ENV" ]; then
    echo "ERROR: Parent .env file not found!"
    echo "Please create .env from .env.example first"
    exit 1
fi

# Check that Bookwyrm directory exists
if [ ! -d "$BOOKWYRM_DIR" ]; then
    echo "ERROR: Bookwyrm directory not found at $BOOKWYRM_DIR"
    exit 1
fi

# Check if .env.example exists in Bookwyrm directory
if [ ! -f "${BOOKWYRM_DIR}/.env.example" ]; then
    echo "ERROR: ${BOOKWYRM_DIR}/.env.example not found"
    echo "The Bookwyrm wrapper may not be properly cloned"
    exit 1
fi

# Load parent environment variables
source "$PARENT_ENV"

# If .env already exists, back it up
if [ -f "$BOOKWYRM_ENV" ]; then
    backup_file="${BOOKWYRM_ENV}.backup.$(date +%Y%m%d-%H%M%S)"
    echo "⚠️  Existing .env found, creating backup: ${backup_file}"
    cp "$BOOKWYRM_ENV" "$backup_file"
fi

# Copy .env.example as base
cp "${BOOKWYRM_DIR}/.env.example" "$BOOKWYRM_ENV"

# Update key configuration values for Traefik integration
echo "Applying Traefik integration settings..."

# Update domain to use .home.local for Traefik
sed -i.bak 's/^BOOKWYRM_DOMAIN=.*/BOOKWYRM_DOMAIN=bookwyrm.home.local/' "$BOOKWYRM_ENV"

# Enable HTTPS (Traefik provides the TLS)
sed -i.bak 's/^BOOKWYRM_USE_HTTPS=.*/BOOKWYRM_USE_HTTPS=true/' "$BOOKWYRM_ENV"

# Apply environment variables from parent .env if they exist
if [ ! -z "$BOOKWYRM_SECRET_KEY" ]; then
    sed -i.bak "s|^BOOKWYRM_SECRET_KEY=.*|BOOKWYRM_SECRET_KEY=${BOOKWYRM_SECRET_KEY}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_DB_USER" ]; then
    sed -i.bak "s|^POSTGRES_USER=.*|POSTGRES_USER=${BOOKWYRM_DB_USER}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_DB_PASSWORD" ]; then
    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${BOOKWYRM_DB_PASSWORD}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_DB_NAME" ]; then
    sed -i.bak "s|^POSTGRES_DB=.*|POSTGRES_DB=${BOOKWYRM_DB_NAME}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_REDIS_ACTIVITY_PASSWORD" ]; then
    sed -i.bak "s|^REDIS_ACTIVITY_PASSWORD=.*|REDIS_ACTIVITY_PASSWORD=${BOOKWYRM_REDIS_ACTIVITY_PASSWORD}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_REDIS_BROKER_PASSWORD" ]; then
    sed -i.bak "s|^REDIS_BROKER_PASSWORD=.*|REDIS_BROKER_PASSWORD=${BOOKWYRM_REDIS_BROKER_PASSWORD}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$TIMEZONE" ]; then
    sed -i.bak "s|^TZ=.*|TZ=${TIMEZONE}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_EMAIL_HOST" ]; then
    sed -i.bak "s|^EMAIL_HOST=.*|EMAIL_HOST=${BOOKWYRM_EMAIL_HOST}|" "$BOOKWYRM_ENV"
fi

if [ ! -z "$BOOKWYRM_EMAIL_PORT" ]; then
    sed -i.bak "s|^EMAIL_PORT=.*|EMAIL_PORT=${BOOKWYRM_EMAIL_PORT}|" "$BOOKWYRM_ENV"
fi

# Clean up backup files created by sed
rm -f "${BOOKWYRM_ENV}.bak"

echo "✓ Bookwyrm .env configured for Traefik integration"
echo "  - Domain: bookwyrm.home.local"
echo "  - HTTPS: enabled (via Traefik)"
echo ""
echo "To customize further, edit: ${BOOKWYRM_ENV}"
