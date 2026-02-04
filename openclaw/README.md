# OpenClaw Docker Image with Homebrew and GOG

This directory contains a custom Dockerfile for OpenClaw with Homebrew and GOG (Google OAuth CLI) preinstalled.

**Important:** This image does NOT preconfigure OpenClaw. You run the interactive setup wizard after building the image.

## What's Included

This custom OpenClaw image includes:

- **Base:** Node.js 22 (Debian Bookworm)
- **OpenClaw CLI:** Installed via official `openclaw.ai/install.sh` script
- **Homebrew (Linuxbrew):** Package manager for installing additional tools
- **GOG (Google OAuth CLI):** Google services integration for Gmail, Calendar, Drive, Docs, Sheets, and Contacts
- **Security:** Runs as non-root `node` user (UID 1000)

## Quick Start

```bash
# 1. Build the image (10-15 minutes first time)
make openclaw-build

# 2. Run the interactive setup wizard
make openclaw-onboard

# 3. Start all services (includes OpenClaw)
make start

# 4. Access the web UI
# Open in browser: http://SERVER_IP:18789
```

**Note:** OpenClaw is integrated with the main service management. Use `make start/stop/restart` to manage it along with all other services.

## Setup Wizard

The `make openclaw-onboard` command runs an interactive wizard that guides you through:

1. **AI Provider Selection:** Choose Anthropic
2. **API Key Configuration:** Enter your Anthropic API key (get from console.anthropic.com)
3. **Model Selection:** Choose claude-sonnet-4-5 (recommended)
4. **Messaging Channels:** Configure Telegram, WhatsApp, Discord, etc.
5. **Gateway Token:** Automatically generated for web UI access

All configuration is saved to `./data/openclaw/config/openclaw.json`.

## Using Homebrew Inside the Container

Once the container is running, you can use Homebrew to install additional tools:

```bash
# Access container shell
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway bash

# Inside container - install packages with Homebrew
brew install jq
brew install gh
brew install python@3.11

# Verify installation
which jq
jq --version
```

## Using GOG (Google OAuth CLI)

GOG enables OpenClaw to interact with Google services:

```bash
# Inside container - authenticate with Google
gog auth login

# Access Gmail
gog gmail list

# Access Calendar
gog calendar list

# Access Drive
gog drive list
```

You can also install GOG-related skills via the OpenClaw web UI:
1. Navigate to Skills section
2. Search for "calendar"
3. Click Install "gog (brew)"

## Environment Variables

See `.env.example` for configuration options:

- `OPENCLAW_GATEWAY_PORT` - Web UI port (default: 18789)
- `OPENCLAW_BRIDGE_PORT` - Bridge API port (default: 18790)
- `OPENCLAW_GATEWAY_BIND` - Bind address (default: 0.0.0.0)
- `OPENCLAW_CONFIG_DIR` - Config directory (default: ./data/openclaw/config)
- `OPENCLAW_WORKSPACE_DIR` - Workspace directory (default: ./data/openclaw/workspace)
- `OPENCLAW_DOCKER_APT_PACKAGES` - Additional system packages to install during build

**Note:** API keys and gateway tokens are configured via the setup wizard, NOT environment variables.

## Data Persistence

The container persists data in two directories:

- `./data/openclaw/config/` - Configuration files (includes openclaw.json with API keys)
- `./data/openclaw/workspace/` - Workspace files

**Important:** These directories contain sensitive information. Never commit them to git.

## Network Access

OpenClaw is **NOT behind Traefik** and uses direct port access:

- Web UI: `http://${SERVER_IP}:18789`
- Bridge API: `http://${SERVER_IP}:18790`

**Security Note:** Ensure firewall rules restrict access to trusted networks (local network and VPN subnet only).

## Common Tasks

### Re-running the Setup Wizard

If you need to reconfigure OpenClaw:

```bash
# Stop all services
make stop

# Backup existing configuration (optional)
cp -r ./data/openclaw/config/ ./data/openclaw/config.backup/

# Re-run the wizard
make openclaw-onboard

# Start all services with new configuration
make start
```

### Viewing Configuration

```bash
# View current configuration
cat ./data/openclaw/config/openclaw.json

# View from inside container
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway \
  cat /home/node/.openclaw/openclaw.json
```

### Accessing Container Shell

```bash
# Interactive shell
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway bash

# Inside shell - useful commands
openclaw --version
brew list
which gog
env | grep PATH
```

## Troubleshooting

### Build Fails

If the build fails, check:

1. Docker has enough disk space (image is ~2GB)
2. Internet connectivity for downloading packages
3. No proxy/firewall blocking access to GitHub or Homebrew

```bash
# Clean build with verbose output
docker compose -f docker-compose.openclaw.yml build --no-cache --progress=plain
```

### Setup Wizard Exits Immediately

If the wizard exits without prompting:

1. Ensure you're running `make openclaw-onboard`, not `make start`
2. Check that stdin/tty are enabled in docker-compose.openclaw.yml
3. Try running manually: `docker compose -f docker-compose.openclaw.yml run --rm openclaw-cli`

### Gateway Won't Start

```bash
# Check if onboarding was completed
ls -la ./data/openclaw/config/
cat ./data/openclaw/config/openclaw.json

# View logs for errors
make logs-openclaw

# Common issue: Configuration file missing or corrupt
# Solution: Re-run setup wizard
make openclaw-onboard
```

### Homebrew Issues

If Homebrew commands don't work inside the container:

```bash
# Access container
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway bash

# Verify Homebrew is in PATH
echo $PATH

# Should show: /home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:...

# If not, manually add to PATH
export PATH="/home/linuxbrew/.linuxbrew/bin:/home/linuxbrew/.linuxbrew/sbin:$PATH"

# Verify installation
brew --version
```

### Messaging Channels Not Working

```bash
# Check configuration
cat ./data/openclaw/config/openclaw.json

# Look for channel configurations
# Verify API keys/tokens are correct

# Test network connectivity from container
docker compose -f docker-compose.openclaw.yml exec openclaw-gateway bash
curl -I https://api.telegram.org

# Re-run setup wizard to reconfigure channels
make stop
make openclaw-onboard
make start
```

## Resource Usage

The OpenClaw container has default resource limits:

- CPU: 2 cores (limit), 0.5 cores (reservation)
- Memory: 4GB (limit), 1GB (reservation)

Adjust these in `docker-compose.openclaw.yml` if needed:

```yaml
deploy:
  resources:
    limits:
      cpus: '4'      # Increase to 4 cores
      memory: 8G     # Increase to 8GB
```

## Development Notes

### Rebuilding After Dockerfile Changes

If you modify the Dockerfile:

```bash
# Rebuild image
make openclaw-build

# Configuration is preserved in ./data/openclaw/
# No need to re-run onboarding

# Restart with new image
make restart
```

### Adding System Packages Permanently

To add system packages that persist across rebuilds:

1. Update `OPENCLAW_DOCKER_APT_PACKAGES` in `.env`:
   ```bash
   OPENCLAW_DOCKER_APT_PACKAGES="ffmpeg python3-pip libmagic1"
   ```

2. Rebuild image:
   ```bash
   make openclaw-build
   ```

### Debugging Build Issues

```bash
# Build with verbose output
docker compose -f docker-compose.openclaw.yml build --no-cache --progress=plain

# Check intermediate layers
docker images | grep openclaw

# Access a build layer for debugging
docker run -it --rm <image-id> bash
```

## References

- [OpenClaw Documentation](https://docs.openclaw.ai)
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [Homebrew Documentation](https://docs.brew.sh)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## Migration from Native Installation

If you have OpenClaw installed natively (systemd service), see `MIGRATION.md` for step-by-step migration instructions.
