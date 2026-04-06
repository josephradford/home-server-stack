#!/bin/bash
set -e

# Ensure persona file exists
if [ ! -f /app/CLAUDE.md ]; then
    echo "ERROR: bede/CLAUDE.md not found."
    echo "Copy the example and fill in your details:"
    echo "  cp bede/CLAUDE.md.example bede/CLAUDE.md"
    exit 1
fi

# Configure SSH key for private vault repos
if [ -f "/home/bede/.ssh/vault_key" ] && [ -s "/home/bede/.ssh/vault_key" ]; then
    chmod 600 /home/bede/.ssh/vault_key
    # Populate known_hosts for common git hosts so StrictHostKeyChecking doesn't block
    ssh-keyscan github.com gitlab.com bitbucket.org >> /home/bede/.ssh/known_hosts 2>/dev/null || true
    export GIT_SSH_COMMAND="ssh -i /home/bede/.ssh/vault_key -o StrictHostKeyChecking=no"
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
