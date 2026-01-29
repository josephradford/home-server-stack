# Moltbot Integration Design

**Date:** 2026-01-30
**Status:** Approved
**Author:** Claude Code

## Overview

This document describes the integration of Moltbot (formerly Clawdbot) into the home-server-stack. Moltbot is an open-source, self-hosted AI assistant that connects messaging apps (Signal, Telegram, WhatsApp, Discord, Slack) to an AI agent running on your server.

### Key Decisions

- **Messaging Platform:** Signal
- **AI Provider:** Anthropic Claude
- **Access Control:** VPN/Local network only (admin-secure middleware)
- **Sandboxing:** Enabled with isolated Docker containers for code execution
- **Deployment:** Docker Compose with Traefik reverse proxy

## Architecture

### Service Structure

- **Container:** `moltbot` running the gateway service
- **Image:** `ghcr.io/moltbot/moltbot:main` (pre-built from GitHub Container Registry)
- **Network:** Connected to `homeserver` bridge network
- **Data Persistence:** Configuration and session data in `./data/moltbot/`

### Integration Points

1. **Traefik Reverse Proxy:**
   - Web UI accessible at `https://moltbot.${DOMAIN}`
   - Uses existing `admin-secure` middleware chain:
     - IP allowlist (local network + VPN only)
     - Security headers (HSTS, XSS protection, frame deny)
     - Rate limiting (100 req/min, burst 50)

2. **AI Provider:**
   - Anthropic Claude API
   - API key stored in `.env` file
   - Costs incurred per API call (monitor via Anthropic console)

3. **Messaging Integration:**
   - Signal integration via QR code device linking
   - Session data persists in `./data/moltbot/signal/`
   - Messages sent to Moltbot contact receive AI-powered responses

4. **Sandbox Execution:**
   - Code runs in isolated `moltbot-sandbox:bookworm-slim` containers
   - Ephemeral containers created per task, destroyed after completion
   - Requires Docker socket access (read-only) for container spawning

## Docker Compose Configuration

### Main Service

```yaml
moltbot:
  image: ghcr.io/moltbot/moltbot:main
  container_name: moltbot
  restart: unless-stopped
  expose:
    - 3000
  environment:
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    - TZ=${TIMEZONE}
    - MOLTBOT_SANDBOX_ENABLED=true
    - MOLTBOT_SANDBOX_IMAGE=moltbot-sandbox:bookworm-slim
  volumes:
    - ./data/moltbot:/app/data
    - /var/run/docker.sock:/var/run/docker.sock:ro
  networks:
    - homeserver
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.moltbot.rule=Host(`moltbot.${DOMAIN}`)"
    - "traefik.http.routers.moltbot.entrypoints=websecure"
    - "traefik.http.routers.moltbot.tls=true"
    - "traefik.http.services.moltbot.loadbalancer.server.port=3000"
    - "traefik.http.routers.moltbot.middlewares=admin-secure"
```

### Environment Variables

Add to `.env`:
```bash
# Moltbot Configuration - AI assistant accessible via Signal
# Accessible via https://moltbot.DOMAIN (VPN/local access only)
# Get API key from: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Setup Process

### 1. Prerequisites

- Anthropic API key from https://console.anthropic.com/settings/keys
- Signal app installed on phone for device linking

### 2. Build Sandbox Image

```bash
# Clone Moltbot repository temporarily
git clone https://github.com/moltbot/moltbot.git /tmp/moltbot
cd /tmp/moltbot

# Build sandbox image
docker build -t moltbot-sandbox:bookworm-slim -f Dockerfile.sandbox .

# Clean up
cd ~
rm -rf /tmp/moltbot
```

### 3. Configure Environment

```bash
# Add API key to .env
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env

# Update .env.example with documentation
```

### 4. Deploy Service

```bash
# Add service to docker-compose.yml
# Start Moltbot
docker compose up -d moltbot

# Verify running
docker ps | grep moltbot
docker logs moltbot
```

### 5. Initial Configuration

1. Access `https://moltbot.${DOMAIN}` from VPN or local network
2. Complete onboarding wizard:
   - Select Anthropic Claude as AI provider
   - Configure Signal integration (QR code)
   - Set preferences

3. Link Signal Device:
   - Open Signal app → Settings → Linked Devices → Link New Device
   - Scan QR code from Moltbot web UI
   - Verify link successful

## Data Storage

All data persists in `./data/moltbot/`:

- **Configuration:** `./data/moltbot/config/` - Settings and preferences
- **Signal Session:** `./data/moltbot/signal/` - Device link data (keeps connection alive)
- **Chat History:** `./data/moltbot/chats/` - Conversation logs
- **Sandbox Data:** Ephemeral (created/destroyed per task)

## Security

### Security Measures

1. **Network Isolation:**
   - Traefik `admin-secure` middleware blocks all non-local/VPN traffic
   - Only accessible from 192.168.0.0/16 (local) or 10.0.0.0/8 (VPN)
   - Rate limited to 100 requests/minute

2. **Sandbox Isolation:**
   - Code executes in ephemeral Docker containers
   - Sandbox containers have no access to host filesystem
   - Automatically destroyed after task completion

3. **Container Isolation:**
   - Runs in Docker with limited host access
   - Only Docker socket (read-only) and data volume mounted
   - No privileged mode or excessive capabilities

4. **API Key Security:**
   - Anthropic key in `.env` file (gitignored)
   - Never committed to repository
   - Passed as environment variable only

### Known Security Considerations

- **Prompt Injection:** Malicious Signal messages could theoretically trick AI into harmful actions. Mitigated by sandboxing and network isolation.
- **Signal Session:** If `./data/moltbot/signal/` compromised, attacker could read Signal messages to Moltbot. Keep backups secure.
- **API Costs:** Unauthorized usage could incur API costs. Monitor Anthropic console for unusual activity.
- **Docker Socket Access:** Container can spawn other containers. Sandboxing required for untrusted code execution.

### Recommendations

- Regularly review logs: `docker logs moltbot`
- Monitor Anthropic API usage for unexpected spikes
- Keep WireGuard VPN credentials secure
- Backup `./data/moltbot/` regularly, especially Signal session data
- Consider implementing API usage alerts via Prometheus

## Testing and Verification

### Basic Health Checks

```bash
# Container status
docker ps | grep moltbot

# Check logs
docker logs moltbot

# Verify Traefik routing
# Visit https://traefik.${DOMAIN} and check for moltbot@docker router
```

### Web UI Access Test

1. Connect to WireGuard VPN or use local network
2. Navigate to `https://moltbot.${DOMAIN}`
3. Should see Moltbot dashboard (not blocked by Traefik)

### Signal Integration Test

1. Link Signal device via QR code
2. Send test message: "Hello Moltbot"
3. Verify response received (may take 5-10 seconds)
4. Check logs for message handling

### Sandbox Test

1. Ask Moltbot via Signal: "Write a Python script that prints hello world and run it"
2. During execution, check: `docker ps -a` (should see temporary sandbox)
3. Verify sandbox removed after completion
4. Check logs for sandbox creation/destruction

### Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Can't access web UI | Not on VPN/local network | Connect to WireGuard or use local network |
| Signal not responding | Session expired or not linked | Re-link device via QR code |
| Sandbox errors | Image not built | Build sandbox image from Dockerfile.sandbox |
| API errors | Invalid or missing key | Check ANTHROPIC_API_KEY in .env |

## Makefile Integration

Moltbot will integrate with existing Makefile commands:

- `make start` - Starts Moltbot with other services
- `make stop` - Stops Moltbot
- `make restart` - Restarts Moltbot
- `make logs` - Shows all logs including Moltbot
- `make update` - Pulls latest Moltbot image

Specific commands:
```bash
# Start only Moltbot
docker compose up -d moltbot

# View Moltbot logs
docker logs -f moltbot

# Restart Moltbot
docker compose restart moltbot
```

## Future Enhancements

- **Additional Messaging Platforms:** Enable Telegram, Discord, or WhatsApp
- **Browser Sandbox:** Build `moltbot-sandbox-browser:bookworm-slim` for web automation tasks
- **Prometheus Monitoring:** Add metrics for message counts, API usage, sandbox spawns
- **Homepage Dashboard Widget:** Display Moltbot status and recent activity
- **Multiple AI Providers:** Configure fallback providers (OpenAI, local Ollama)

## References

- [Moltbot Official Documentation](https://docs.molt.bot/)
- [Moltbot Docker Installation](https://docs.molt.bot/install/docker)
- [Moltbot GitHub Repository](https://github.com/moltbot/moltbot)
- [Moltbot Docker Images](https://github.com/moltbot/moltbot/pkgs/container/moltbot)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Signal Linked Devices](https://support.signal.org/hc/en-us/articles/360007320551-Linked-Devices)

## Conclusion

This design integrates Moltbot into the home-server-stack following established security and architectural patterns. The service will be accessible only via VPN or local network, use sandboxed code execution, and integrate seamlessly with existing Traefik routing and middleware.
