#!/bin/bash
set -e

echo "🏠 Setting up Homepage Dashboard"
echo "================================"

# Create config directory
mkdir -p data/homepage/config

# Copy template config files if they don't exist
if [ ! -f "data/homepage/config/services.yaml" ]; then
    echo "📋 Copying services.yaml template..."
    if [ -f "config/homepage/services.yaml" ]; then
        cp config/homepage/services.yaml data/homepage/config/services.yaml
    else
        echo "⚠️  Template not found: config/homepage/services.yaml"
        echo "    Please create config templates in config/homepage/"
        exit 1
    fi
fi

# Check if other required config files exist
for config_file in settings.yaml widgets.yaml docker.yaml bookmarks.yaml; do
    if [ ! -f "data/homepage/config/$config_file" ]; then
        echo "⚠️  Missing config file: data/homepage/config/$config_file"
        echo "    Please ensure all config files are created manually or from templates"
        exit 1
    fi
done

# Check Docker network
if ! docker network inspect home-server &>/dev/null; then
    echo "📡 Creating Docker network..."
    docker network create home-server
fi

echo "🚀 Starting Homepage..."
docker compose -f docker-compose.dashboard.yml up -d homepage

echo "✅ Homepage is running at http://$(grep SERVER_IP .env | cut -d '=' -f2):3100"
