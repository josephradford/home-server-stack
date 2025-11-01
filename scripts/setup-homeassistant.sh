#!/bin/bash
# Home Assistant Configuration Setup
# Copies configuration templates to data directory

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Home Assistant configuration...${NC}"

# Load environment variables
if [ ! -f .env ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Run: cp .env.example .env"
    echo "Then edit .env with your configuration"
    exit 1
fi

set -a
source .env
set +a

# Verify required variables
if [ -z "$TIMEZONE" ]; then
    echo -e "${YELLOW}WARNING: TIMEZONE not set in .env, using UTC${NC}"
    TIMEZONE="UTC"
fi

# Create data directory
echo "Creating Home Assistant data directory..."
mkdir -p data/homeassistant

# Copy configuration files from template
echo "Copying configuration templates..."
cp config/homeassistant-template/configuration.yaml data/homeassistant/
cp config/homeassistant-template/secrets.yaml.example data/homeassistant/
cp config/homeassistant-template/automations.yaml data/homeassistant/
cp config/homeassistant-template/scripts.yaml data/homeassistant/
cp config/homeassistant-template/scenes.yaml data/homeassistant/

# Create secrets.yaml from example if it doesn't exist
if [ ! -f data/homeassistant/secrets.yaml ]; then
    echo "Creating secrets.yaml from template..."
    cp config/homeassistant-template/secrets.yaml.example data/homeassistant/secrets.yaml
    echo -e "${YELLOW}NOTE: Edit data/homeassistant/secrets.yaml to add your actual location coordinates${NC}"
fi

echo -e "${GREEN}✓ Home Assistant configuration files copied${NC}"
echo ""
echo "Configuration location: ./data/homeassistant/"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Start Home Assistant: docker compose up -d homeassistant"
echo "2. Access at: http://$SERVER_IP:8123"
echo "3. Complete onboarding wizard"
echo "4. Generate API token and add to .env"
echo ""
echo "See docs/HOME_ASSISTANT_SETUP.md for detailed setup instructions"
