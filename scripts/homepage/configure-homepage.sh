#!/bin/bash
set -e

# Configure Homepage Dashboard
# This script copies template YAML files to the Homepage config directory
# Only runs if config files don't already exist (preserves existing configuration)

echo "🏠 Configuring Homepage Dashboard"
echo "=================================="

# Ensure config directory exists
CONFIG_DIR="data/homepage/config"
TEMPLATE_DIR="config/homepage"

mkdir -p "$CONFIG_DIR"

# Check if template directory exists
if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "❌ Error: Template directory not found: $TEMPLATE_DIR"
    echo "   Please ensure config/homepage/ exists with template files"
    exit 1
fi

# List of template files to copy
TEMPLATES=(
    "services.yaml"
    "settings.yaml"
    "widgets.yaml"
    "docker.yaml"
    "bookmarks.yaml"
)

# Check if config files already exist
if [ -f "$CONFIG_DIR/services.yaml" ] && [ -f "$CONFIG_DIR/settings.yaml" ]; then
    echo "ℹ️  Homepage configuration files already exist"
    echo ""
    echo "⚠️  WARNING: Overwriting will replace your existing configuration!"
    echo ""
    echo "Would you like to overwrite them? (y/N)"
    read -r response

    if [ "$response" != "y" ] && [ "$response" != "Y" ]; then
        echo ""
        echo "✓ Keeping existing configuration"
        echo ""
        exit 0
    fi

    echo ""
    echo "📝 Overwriting existing configuration files..."
    echo ""
else
    echo "📝 Creating Homepage configuration files..."
    echo ""
fi

# Copy template files
for template in "${TEMPLATES[@]}"; do
    template_file="$TEMPLATE_DIR/${template%.yaml}-template.yaml"
    target_file="$CONFIG_DIR/${template}"

    if [ ! -f "$template_file" ]; then
        echo "⚠️  Warning: Template not found: $template_file"
        continue
    fi

    echo "  Copying $template..."
    cp "$template_file" "$target_file"
done

echo ""
echo "✅ Homepage configuration complete!"
echo ""
echo "Configuration files written to $CONFIG_DIR/"
for template in "${TEMPLATES[@]}"; do
    if [ -f "$CONFIG_DIR/$template" ]; then
        echo "  ✓ $template"
    fi
done
echo ""
echo "Special features:"
echo "  - BOM Weather widget (using homepage-api)"
echo "  - Docker container monitoring"
echo "  - AdGuard Home widget"
echo "  - Grafana widget"
