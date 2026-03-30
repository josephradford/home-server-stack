#!/bin/bash
set -e

# Configure OpenClaw AI Assistant
# Renders openclaw.json.template → data/openclaw/openclaw.json using envsubst
# Called during 'make setup' as Step 4/9

echo "🦅 Configuring OpenClaw AI Assistant"
echo "======================================"

# Load environment variables
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    exit 1
fi

set -a
source .env
set +a

TEMPLATE="config/openclaw/openclaw.json.template"
OUTPUT_DIR="data/openclaw"
OUTPUT="$OUTPUT_DIR/openclaw.json"

# Check template exists
if [ ! -f "$TEMPLATE" ]; then
    echo "❌ Error: Template not found: $TEMPLATE"
    exit 1
fi

# Check required variables
missing_vars=()
[ -z "$OPENCLAW_GATEWAY_TOKEN" ] && missing_vars+=("OPENCLAW_GATEWAY_TOKEN")
[ -z "$ANTHROPIC_API_KEY" ] && missing_vars+=("ANTHROPIC_API_KEY")
[ -z "$TELEGRAM_BOT_TOKEN" ] && missing_vars+=("TELEGRAM_BOT_TOKEN")

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Error: Missing required variables in .env:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Add these to your .env file and re-run setup."
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Render template
envsubst < "$TEMPLATE" > "$OUTPUT"

# Set permissions: readable by owner and group only (config contains secrets)
chmod 640 "$OUTPUT"

echo "✓ OpenClaw config rendered to $OUTPUT"
