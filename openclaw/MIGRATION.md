# Migrating OpenClaw from Native Installation to Docker

This guide helps you migrate from a native OpenClaw installation (systemd service) to the Docker-based deployment.

## Prerequisites

- Existing native OpenClaw installation running on your server
- Docker and Docker Compose installed
- Access to your server via SSH
- Current `.env` file configured

## Migration Steps

### 1. Backup Your Existing Configuration

Before making any changes, back up your existing OpenClaw configuration:

```bash
# SSH to your server
ssh user@SERVER_IP

# Create backup directory
mkdir -p ~/openclaw-backup

# Backup OpenClaw configuration
cp -r ~/.openclaw ~/openclaw-backup/
cp -r ~/.openclaw/workspace ~/openclaw-backup/ 2>/dev/null || true

# Verify backup
ls -la ~/openclaw-backup/
```

### 2. Stop the Native OpenClaw Service

```bash
# Stop the systemd service
openclaw gateway stop

# Verify it's stopped
systemctl --user status openclaw-gateway

# Disable auto-start (optional)
systemctl --user disable openclaw-gateway
```

### 3. Export Your Configuration Values

Extract values from your native configuration:

```bash
# View your current OpenClaw configuration
cat ~/.openclaw/openclaw.json

# Note down:
# - Your Anthropic API key
# - Your messaging channel configurations (Telegram, WhatsApp, etc.)
# - Any custom settings
```

### 4. Configure Environment Variables

On your development machine, update your `.env` file:

```bash
# Edit .env file
nano .env

# Add/update these variables:
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)  # Generate a new token
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790
OPENCLAW_GATEWAY_BIND=0.0.0.0
OPENCLAW_CONFIG_DIR=./data/openclaw/config
OPENCLAW_WORKSPACE_DIR=./data/openclaw/workspace
```

### 5. Copy Configuration to Data Directory

On your server, copy the existing configuration to the Docker data directory:

```bash
# Create data directories
mkdir -p ./data/openclaw/config
mkdir -p ./data/openclaw/workspace

# Copy configuration from native installation
cp -r ~/.openclaw/* ./data/openclaw/config/
cp -r ~/.openclaw/workspace/* ./data/openclaw/workspace/ 2>/dev/null || true

# Set proper permissions
sudo chown -R $(id -u):$(id -g) ./data/openclaw/
chmod -R 755 ./data/openclaw/
```

### 6. Build and Start OpenClaw Docker Container

```bash
# Build the Docker image (from dev machine or server)
make openclaw-build

# Start the container
make openclaw-start

# Check status
make openclaw-status

# View logs
make openclaw-logs
```

### 7. Verify the Migration

```bash
# Check that OpenClaw is running
docker compose -f docker-compose.openclaw.yml ps

# Access the web UI
# Open in browser: http://SERVER_IP:18789

# Paste your gateway token (from .env: OPENCLAW_GATEWAY_TOKEN)

# Test your messaging channels
# Send a message to your Telegram bot or WhatsApp number
```

### 8. Update Messaging Channel Configurations (if needed)

If your messaging channels (Telegram, WhatsApp, Discord) were configured with webhooks pointing to specific URLs, you may need to update them:

- **Telegram (Long-Polling):** No changes needed - this is the default mode
- **Telegram (Webhook):** Update webhook URL if needed (usually not necessary)
- **WhatsApp:** Check that the connection still works
- **Discord:** Verify bot is still responding

### 9. Clean Up Native Installation (Optional)

Once you've verified the Docker installation works correctly:

```bash
# On your server
ssh user@SERVER_IP

# Uninstall native OpenClaw (optional)
npm uninstall -g openclaw

# Remove systemd service files
rm ~/.config/systemd/user/openclaw-gateway.service
systemctl --user daemon-reload

# Keep backup in case you need to roll back
# ~/openclaw-backup/
```

## Rollback Procedure

If you encounter issues with the Docker installation:

```bash
# 1. Stop Docker container
make openclaw-stop

# 2. On your server, restore native configuration
ssh user@SERVER_IP
cp -r ~/openclaw-backup/.openclaw ~/

# 3. Restart native service
openclaw gateway start
systemctl --user status openclaw-gateway
```

## Differences Between Native and Docker Installations

| Aspect | Native Installation | Docker Installation |
|--------|-------------------|-------------------|
| **Installation** | Manual via curl script | Docker build from Dockerfile |
| **Updates** | `openclaw update` | Rebuild Docker image |
| **Configuration** | `~/.openclaw/` | `./data/openclaw/config/` |
| **Logs** | `journalctl --user -u openclaw-gateway` | `make openclaw-logs` |
| **Management** | `openclaw` CLI commands | `make openclaw-*` commands |
| **Tools** | Manual installation | Homebrew + GOG preinstalled |
| **Isolation** | System-level | Container-level |
| **Backup** | `~/.openclaw/` directory | `./data/openclaw/` directory |

## Advantages of Docker Installation

1. **Isolation:** Container is isolated from the host system
2. **Reproducibility:** Same image works on any Docker host
3. **Pre-installed Tools:** Homebrew and GOG come preinstalled
4. **Easy Updates:** Rebuild image to update
5. **Consistent Environment:** Same Node.js version and dependencies
6. **Resource Limits:** Can set CPU and memory limits
7. **Easier Backup:** Data in `./data/openclaw/` directory

## Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
make openclaw-logs

# Verify environment variables are set
grep OPENCLAW .env
grep ANTHROPIC .env

# Check that data directories exist
ls -la ./data/openclaw/
```

### Messaging Channels Not Working

```bash
# Access container shell
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway bash

# Inside container - check configuration
cat /home/node/.openclaw/openclaw.json

# Verify network connectivity
curl -I https://api.telegram.org
```

### Configuration Not Persisted

```bash
# Verify volume mounts
docker compose -f docker-compose.openclaw.yml config | grep volumes -A 5

# Check directory permissions
ls -la ./data/openclaw/

# Ensure paths are correct in docker-compose.openclaw.yml
```

### Homebrew Commands Don't Work

```bash
# Access container
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway bash

# Check Homebrew PATH
echo $PATH

# Verify Homebrew installation
ls -la /home/linuxbrew/.linuxbrew/bin/brew

# Try running brew
/home/linuxbrew/.linuxbrew/bin/brew --version
```

## Support

If you encounter issues during migration:

1. Check the logs: `make openclaw-logs`
2. Verify configuration: `cat ./data/openclaw/config/openclaw.json`
3. Review the OpenClaw documentation: https://docs.openclaw.ai
4. Check Docker logs: `docker compose -f docker-compose.openclaw.yml logs`

For issues specific to this Docker setup, refer to:
- `openclaw/README.md` - Docker image documentation
- `CLAUDE.md` - Project-wide documentation
- `.env.example` - Configuration examples
