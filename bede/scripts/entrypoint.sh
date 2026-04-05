#!/bin/bash
set -e

# Ensure persona file exists
if [ ! -f /app/CLAUDE.md ]; then
    echo "ERROR: bede/CLAUDE.md not found."
    echo "Copy the example and fill in your details:"
    echo "  cp bede/CLAUDE.md.example bede/CLAUDE.md"
    exit 1
fi

# Pull Obsidian vault if VAULT_REPO is configured (Phase 2)
if [ -n "${VAULT_REPO}" ]; then
    if [ -d "/vault/.git" ]; then
        echo "[entrypoint] Pulling vault..."
        git -C /vault pull --ff-only || echo "[entrypoint] Vault pull failed — continuing with existing state"
    else
        echo "[entrypoint] Cloning vault..."
        git clone "${VAULT_REPO}" /vault
    fi
fi

echo "[entrypoint] Starting supervisord..."
exec supervisord -c /app/supervisord.conf
