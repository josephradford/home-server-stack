#!/bin/bash
set -e

echo "🏠 Setting up Homepage Dashboard"
echo "================================"

# Create config directory
mkdir -p data/homepage/config

# Check if config files exist
if [ ! -f "data/homepage/config/settings.yaml" ]; then
    echo "⚠️  Config files not found. Please ensure all YAML files are in place."
    exit 1
fi

# Check Docker network
if ! docker network inspect home-server &>/dev/null; then
    echo "📡 Creating Docker network..."
    docker network create home-server
fi

echo "🚀 Starting Homepage..."
docker compose -f docker-compose.dashboard.yml up -d homepage

echo "✅ Homepage is running at http://$(grep SERVER_IP .env | cut -d '=' -f2):3100"
