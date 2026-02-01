# Moltbot Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Moltbot AI assistant to home-server-stack with Signal integration, Anthropic Claude AI provider, sandboxed code execution, and VPN/local-only access.

**Architecture:** Moltbot runs as a Docker service integrated with Traefik reverse proxy using admin-secure middleware for VPN/local access. Code execution happens in ephemeral sandbox containers spawned via Docker socket. Signal device linking via QR code in web UI.

**Tech Stack:** Docker, Docker Compose, Traefik, Moltbot (ghcr.io/moltbot/moltbot:main), Anthropic Claude API, Signal

---

## Task 1: Build Moltbot Sandbox Image

**Files:**
- Read: N/A (external repository)
- Create: Local Docker image `moltbot-sandbox:bookworm-slim`

**Context:** Moltbot requires a sandbox image for isolated code execution. We need to build this from the official Moltbot repository's Dockerfile.sandbox.

**Step 1: Clone Moltbot repository temporarily**

```bash
git clone https://github.com/moltbot/moltbot.git /tmp/moltbot-build
```

Expected: Repository cloned successfully to `/tmp/moltbot-build`

**Step 2: Build sandbox image**

```bash
cd /tmp/moltbot-build
docker build -t moltbot-sandbox:bookworm-slim -f Dockerfile.sandbox .
```

Expected: Image builds successfully (may take 5-10 minutes)
Expected output includes: `Successfully tagged moltbot-sandbox:bookworm-slim`

**Step 3: Verify image exists**

```bash
docker images | grep moltbot-sandbox
```

Expected output:
```
moltbot-sandbox    bookworm-slim    <image_id>    <time>    <size>
```

**Step 4: Clean up temporary repository**

```bash
cd ~
rm -rf /tmp/moltbot-build
```

Expected: Directory removed, no errors

**Step 5: Commit progress documentation**

This step doesn't modify code files, but we'll document it was completed. No git commit needed yet.

---

## Task 2: Add Moltbot Service to Docker Compose

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/docker-compose.yml`

**Context:** Add Moltbot service definition following existing patterns (n8n, Mealie, Actual Budget). The service will use admin-secure middleware for VPN/local access and mount Docker socket for sandbox spawning.

**Step 1: Read current docker-compose.yml**

Read the file to understand the current structure and where to add Moltbot service.

**Step 2: Add Moltbot service definition**

Add the following service after the `mealie:` service definition in `docker-compose.yml`:

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
      # Using file provider certificate (wildcard from certbot)
      - "traefik.http.services.moltbot.loadbalancer.server.port=3000"
      # Security: VPN/Local access only - AI assistant should be private
      - "traefik.http.routers.moltbot.middlewares=admin-secure"
```

Insert this after line 169 (after the `mealie:` service closes).

**Step 3: Verify YAML syntax**

```bash
docker compose config --quiet
```

Expected: No errors (warnings about missing .env variables are OK)

**Step 4: Update comments in docker-compose.yml header**

Modify the header comment block (lines 2-8) to include Moltbot:

```yaml
---
# Core Services
# This file contains the primary user-facing services
# - AdGuard Home: Network-wide ad blocking and DNS server
# - n8n: Workflow automation platform
# - Home Assistant: Location tracking and home automation
# - Actual Budget: Personal finance and budgeting
# - Mealie: Meal planning and recipe management
# - Moltbot: AI assistant accessible via Signal/Telegram/WhatsApp
```

**Step 5: Commit the changes**

```bash
git add docker-compose.yml
git commit -m "feat: add Moltbot AI assistant service

Adds Moltbot service with:
- Anthropic Claude AI provider integration
- Sandboxed code execution (moltbot-sandbox:bookworm-slim)
- VPN/local-only access via admin-secure middleware
- Traefik reverse proxy at moltbot.DOMAIN
- Docker socket access for spawning sandbox containers
- Data persistence in ./data/moltbot/

Supports Signal, Telegram, WhatsApp, Discord, and Slack messaging.
Configuration via web UI after deployment.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit successful

---

## Task 3: Update .env.example with Moltbot Configuration

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/.env.example`

**Context:** Add comprehensive documentation for Moltbot configuration including Anthropic API key setup instructions.

**Step 1: Read current .env.example**

Read the file to find the appropriate location (after Mealie section, before end of file).

**Step 2: Add Moltbot configuration section**

Add the following at line 265 (after Mealie documentation ends):

```bash
# Moltbot Configuration - AI assistant accessible via messaging apps
# Accessible via https://moltbot.DOMAIN (VPN/local access only)
#
# Moltbot is a self-hosted AI assistant that connects messaging apps (Signal, Telegram,
# WhatsApp, Discord, Slack) to an AI agent running on your server. Think of it as your
# own personal AI assistant that you control completely.
#
# Features:
#   - AI-powered chat via Signal, Telegram, WhatsApp, Discord, or Slack
#   - Code execution in isolated sandbox containers
#   - File operations, system commands, web browsing capabilities
#   - Context-aware conversations with history
#   - Secure, private, self-hosted (no data sent to third parties except AI provider)
#
# ANTHROPIC_API_KEY: API key for Claude AI provider
# Get your API key from: https://console.anthropic.com/settings/keys
#   1. Sign up or log in to Anthropic Console
#   2. Go to Settings → API Keys
#   3. Click "Create Key"
#   4. Copy the key (starts with sk-ant-api03-...)
#   5. Paste below
#
# API Costs (pay-per-use):
#   - Claude 3.5 Sonnet: ~$3 per million input tokens, ~$15 per million output tokens
#   - Typical message: $0.01-0.05 depending on length and complexity
#   - Monitor usage at: https://console.anthropic.com/settings/usage
#
# IMPORTANT: Keep this key secure! Anyone with this key can use your Anthropic account.
# Never commit this key to git (it's already in .gitignore via .env)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# First-time setup after deployment:
#   1. Start Moltbot: docker compose up -d moltbot
#   2. Access web UI: https://moltbot.DOMAIN (from VPN or local network)
#   3. Complete onboarding wizard (select Anthropic Claude as provider)
#   4. Link messaging app:
#      - Signal: Settings → Linked Devices → Link New Device → Scan QR code
#      - Telegram: Create bot via @BotFather → Add bot token to Moltbot
#      - WhatsApp: Scan QR code in Moltbot web UI
#   5. Send test message to verify connection
#
# Data storage (persists across restarts):
#   - Configuration: ./data/moltbot/config/
#   - Messaging sessions: ./data/moltbot/sessions/ (keeps device linked)
#   - Chat history: ./data/moltbot/chats/
#
# Sandbox execution:
#   - Code runs in isolated Docker containers (moltbot-sandbox:bookworm-slim)
#   - Containers created on-demand and destroyed after execution
#   - Prevents malicious code from accessing host system
#   - Check running sandboxes: docker ps | grep moltbot-sandbox
#
# Security:
#   - Admin-secure middleware: VPN or local network access only
#   - No public internet access (reduces attack surface)
#   - Rate limited: 100 requests/minute
#   - Sandbox isolation for code execution
#
# Troubleshooting:
#   - Can't access web UI: Verify VPN connection or use local network
#   - Signal not responding: Check logs (docker logs moltbot), may need to re-link
#   - API errors: Verify ANTHROPIC_API_KEY is correct and has credits
#   - Sandbox errors: Verify moltbot-sandbox:bookworm-slim image exists (docker images)
#
# Optional environment variables (advanced):
# MOLTBOT_SANDBOX_ENABLED=true  # Already set in docker-compose.yml
# MOLTBOT_SANDBOX_IMAGE=moltbot-sandbox:bookworm-slim  # Already set
# MOLTBOT_LOG_LEVEL=info  # Options: debug, info, warn, error
# MOLTBOT_MAX_CONTEXT_MESSAGES=50  # Chat history context window
```

**Step 3: Verify .env.example syntax**

```bash
# Check for common issues
grep "ANTHROPIC_API_KEY" .env.example
```

Expected: Shows the newly added line with correct format

**Step 4: Commit the changes**

```bash
git add .env.example
git commit -m "docs: add Moltbot configuration to .env.example

Adds comprehensive documentation for Moltbot AI assistant including:
- Anthropic API key setup instructions with link to console
- API cost information and monitoring guidance
- First-time setup steps for Signal/Telegram/WhatsApp linking
- Data storage locations and persistence information
- Sandbox execution details
- Security configuration (VPN/local-only, rate limiting)
- Troubleshooting common issues

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit successful

---

## Task 4: Create Data Directory Structure

**Files:**
- Create: `/Users/joeradford/dev/home-server-stack/data/moltbot/.gitkeep`

**Context:** Create the data directory for Moltbot to ensure it exists before first run. The .gitkeep file ensures the directory structure is tracked in git while the actual data contents remain gitignored.

**Step 1: Create moltbot data directory**

```bash
mkdir -p data/moltbot
```

Expected: Directory created (no output if successful)

**Step 2: Add .gitkeep file**

```bash
touch data/moltbot/.gitkeep
```

Expected: File created

**Step 3: Verify directory structure**

```bash
ls -la data/moltbot/
```

Expected output:
```
total 0
drwxr-xr-x  3 user  staff   96 Jan 30 07:30 .
drwxr-xr-x  N user  staff  NNN Jan 30 07:30 ..
-rw-r--r--  1 user  staff    0 Jan 30 07:30 .gitkeep
```

**Step 4: Commit the directory structure**

```bash
git add data/moltbot/.gitkeep
git commit -m "chore: create data directory for Moltbot

Adds data/moltbot/ directory with .gitkeep to track structure.
Actual data contents (config, sessions, chats) remain gitignored.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit successful

---

## Task 5: Update README.md with Moltbot Documentation

**Files:**
- Modify: `/Users/joeradford/dev/home-server-stack/README.md`

**Context:** Add Moltbot to the services list in the main README to document its availability.

**Step 1: Read current README.md**

Identify where to add Moltbot in the services list (should be in Core Services section).

**Step 2: Add Moltbot to Core Services list**

Modify the Core Services section (around line 11) to include Moltbot:

```markdown
**Core Services:**
- **[AdGuard Home](https://github.com/AdguardTeam/AdGuardHome)** - Network-wide ad blocking and DNS server
- **[n8n](https://github.com/n8n-io/n8n)** - Workflow automation platform
- **[Moltbot](https://github.com/moltbot/moltbot)** - AI assistant accessible via Signal/Telegram/WhatsApp
- **[WireGuard](https://github.com/wireguard)** - VPN for secure remote access
- **[Traefik](https://github.com/traefik/traefik)** - Reverse proxy for domain-based service access
```

**Step 3: Add Moltbot to Access Services list**

Add Moltbot to the access list (around line 60):

```markdown
- **n8n:** `https://n8n.${DOMAIN}` (Workflow automation)
- **Moltbot:** `https://moltbot.${DOMAIN}` (AI assistant)
- **Grafana:** `https://grafana.${DOMAIN}` (Monitoring)
```

**Step 4: Verify markdown formatting**

```bash
# Quick visual check
head -80 README.md | tail -30
```

Expected: Shows the updated services list with proper formatting

**Step 5: Commit the changes**

```bash
git add README.md
git commit -m "docs: add Moltbot to README services list

Adds Moltbot to Core Services and access URLs documentation.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: Commit successful

---

## Task 6: Validation and Testing

**Files:**
- Read: Various files for validation

**Context:** Validate the complete implementation before deployment. This ensures all configuration is correct and the service can start successfully.

**Step 1: Validate Docker Compose configuration**

```bash
docker compose config --quiet
```

Expected: No errors (warnings about .env variables are OK)

**Step 2: Verify sandbox image exists**

```bash
docker images | grep moltbot-sandbox
```

Expected: Shows `moltbot-sandbox:bookworm-slim` image

**Step 3: Check git status**

```bash
git status
```

Expected: "working tree clean" (all changes committed)

**Step 4: Review commit history**

```bash
git log --oneline -6
```

Expected: Shows all 5 commits from this implementation:
1. Create data directory for Moltbot
2. Add Moltbot configuration to .env.example
3. Add Moltbot AI assistant service
4. Add Moltbot to README services list
5. Create data directory for Moltbot

**Step 5: Document validation complete**

No commit needed - validation successful.

---

## Post-Implementation Steps (Manual)

These steps must be performed after merging to main branch:

### 1. Set Anthropic API Key

```bash
# On production server
nano .env
# Add line: ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

### 2. Deploy Moltbot

```bash
# Pull latest code
git pull origin main

# Build sandbox image (one-time)
git clone https://github.com/moltbot/moltbot.git /tmp/moltbot-build
cd /tmp/moltbot-build
docker build -t moltbot-sandbox:bookworm-slim -f Dockerfile.sandbox .
cd ~
rm -rf /tmp/moltbot-build

# Start service
docker compose up -d moltbot

# Check status
docker ps | grep moltbot
docker logs moltbot
```

### 3. Configure via Web UI

1. Access `https://moltbot.${DOMAIN}` from VPN or local network
2. Complete onboarding wizard
3. Select Anthropic Claude as AI provider
4. Configure Signal integration (scan QR code with Signal app)

### 4. Verify Integration

1. Send test message via Signal: "Hello Moltbot"
2. Verify response received
3. Test code execution: "Write a Python script that prints hello world and run it"
4. Check sandbox containers: `docker ps -a | grep moltbot-sandbox`
5. Verify sandbox cleanup after execution

### 5. Monitor Performance

- Check logs: `docker logs -f moltbot`
- Monitor API usage: https://console.anthropic.com/settings/usage
- Check Traefik dashboard: `https://traefik.${DOMAIN}` for routing status

---

## Rollback Plan

If issues occur after deployment:

```bash
# Stop Moltbot
docker compose stop moltbot

# Remove container
docker compose rm -f moltbot

# (Optional) Remove image
docker rmi ghcr.io/moltbot/moltbot:main

# Revert code changes
git revert <commit-hash>
```

---

## Success Criteria

- ✅ Sandbox image built successfully (`moltbot-sandbox:bookworm-slim`)
- ✅ Moltbot service added to `docker-compose.yml` with correct configuration
- ✅ `.env.example` updated with comprehensive documentation
- ✅ Data directory structure created (`data/moltbot/`)
- ✅ README.md updated with Moltbot in services list
- ✅ All changes committed with descriptive messages
- ✅ Docker Compose configuration validates successfully
- ✅ Git working tree clean (no uncommitted changes)

Post-deployment success criteria:
- ✅ Moltbot container starts without errors
- ✅ Web UI accessible at `https://moltbot.${DOMAIN}` from VPN/local network
- ✅ Signal device linking successful (QR code scan)
- ✅ Test messages receive AI responses
- ✅ Sandbox containers spawn and cleanup correctly
- ✅ Traefik routing configured (visible in dashboard)

---

## Notes

- **DRY Principle:** Reuse existing `admin-secure` middleware chain (no duplication)
- **YAGNI Principle:** Only Signal initially (other platforms can be added later via UI)
- **Security:** VPN/local-only access prevents public internet exposure
- **API Costs:** Monitor Anthropic usage to avoid unexpected charges
- **Sandbox Images:** Consider building additional sandbox variants later:
  - `moltbot-sandbox-browser:bookworm-slim` for web automation
  - `moltbot-sandbox-common:bookworm-slim` with build tools

## References

- Design Document: `docs/plans/2026-01-30-moltbot-integration-design.md`
- Moltbot Documentation: https://docs.molt.bot/
- Anthropic API Docs: https://docs.anthropic.com/
- Traefik Middleware Reference: `docker-compose.network.yml:119`
