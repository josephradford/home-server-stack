# Bede — Personal AI Assistant

Telegram bot wrapping Claude Code CLI. Runs in Docker on the home server.

## Quick Start

### Prerequisites

1. **Telegram bot token** — create via [@BotFather](https://t.me/BotFather)
2. **Your Telegram user ID** — message [@userinfobot](https://t.me/userinfobot)
3. **Claude credentials on the server** — sync from Mac (see below)

### First-time setup

**1. Add to `.env` on the server:**
```env
TELEGRAM_BOT_TOKEN=your_token_here
ALLOWED_USER_ID=your_numeric_id_here
VAULT_REPO=           # git URL for your Obsidian vault
VAULT_SSH_KEY_PATH=   # host path to SSH key (leave blank for HTTPS PAT)
SESSION_TIMEOUT_MINUTES=10

# Google Workspace MCP
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://SERVER_IP:8765/oauth2callback
```

**2. Sync Claude OAuth credentials from Mac to server:**
```bash
security find-generic-password -s "Claude Code-credentials" -w | \
  ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"
```

**3. Create your persona file** — `bede/CLAUDE.md` is gitignored (it's personal). Copy the example and fill in your details:
```bash
cp bede/CLAUDE.md.example bede/CLAUDE.md
# Edit bede/CLAUDE.md — set your name, location, timezone, role, interests
```

**4. Build and start:**
```bash
make bede-build
make bede-start
make logs-bede
```

## Day-to-day Commands

```bash
make bede-start       # Start Bede + workspace-mcp
make bede-stop        # Stop both containers
make bede-restart     # Restart both containers
make bede-status      # Show container status
make logs-bede        # Tail Bede logs
make bede-build       # Rebuild after code changes, then make bede-start
```

## Telegram Commands

- `/start` — greeting and available commands
- `/reset` — clear the current session (start a fresh conversation)

## Re-authenticating (when OAuth token expires)

Claude Code refreshes tokens automatically — the credentials file is mounted read-write so it can write updated tokens back to the host. You should rarely need to re-authenticate manually.

If Bede does stop responding with an auth error (e.g. after a very long gap), run from your Mac:

```bash
security find-generic-password -s "Claude Code-credentials" -w | \
  ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"
```

No container restart needed — the credentials file is bind-mounted live.

## Setting Up the Obsidian Vault

### HTTPS PAT (simpler)

Set `VAULT_REPO` to a URL with your PAT embedded:
```
VAULT_REPO=https://<PAT>@github.com/you/obsidian-vault.git
```

Leave `VAULT_SSH_KEY_PATH` blank.

### SSH key (private repo without PAT)

1. Generate a dedicated key on the server:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/bede_vault_key -N "" -C "bede@home-server"
   ```
2. Add the public key as a deploy key on your vault repo (read-only is fine).
3. Set in `.env`:
   ```
   VAULT_REPO=git@github.com:you/obsidian-vault.git
   VAULT_SSH_KEY_PATH=/home/user/.ssh/bede_vault_key
   ```

The vault is cloned on container start and pulled before each Claude invocation.

## Setting Up Google Workspace MCP (Gmail, Calendar, Tasks)

The `workspace-mcp` sidecar provides Bede with access to your Google Workspace via MCP tools.

### 1. Create Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or reuse an existing one)
3. Enable APIs: **Gmail API**, **Google Calendar API**, **Google Tasks API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Add authorised redirect URI: `https://mcp.YOUR_DOMAIN/oauth2callback`
7. Copy the **Client ID** and **Client Secret** into `.env`

### 2. Set env vars

```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

The redirect URI (`https://mcp.YOUR_DOMAIN/oauth2callback`) is set automatically from `DOMAIN`.

### 3. Complete the OAuth flow

After starting the stack, from your browser (connected via VPN or local network):

1. Visit `https://mcp.YOUR_DOMAIN` — workspace-mcp will redirect you to Google's consent screen
2. Sign in with the Google account you want Bede to access
3. Approve the requested permissions
4. You'll be redirected back — tokens are saved to the `workspace-mcp-tokens` Docker volume

This is a one-time step. Tokens are refreshed automatically.

> **Note:** `mcp.YOUR_DOMAIN` is protected by `admin-secure-no-ratelimit` middleware — only accessible from your local network or VPN.

## Architecture

```
docker-compose.ai.yml
├── bede container
│   ├── supervisord (PID 1)
│   │   ├── bot.py          — Telegram long-polling
│   │   └── supercronic     — scheduled briefings (Phase 3)
│   ├── claude CLI          — installed via official installer
│   ├── /vault              — Obsidian vault (named volume, git clone on start)
│   └── ~/.claude/.credentials.json  ← bind-mounted from host
└── workspace-mcp container
    ├── workspace-mcp       — pip install workspace-mcp
    ├── port 8765           — OAuth browser flow (VPN/local only)
    └── /data               — OAuth tokens (named volume, persisted)
```

Claude Code auto-discovers workspace-mcp via `.mcp.json` in the working directory, which points to `http://workspace-mcp:8000/mcp` on the internal Docker network. Sessions are resumable because MCP is configured via the project file rather than the `--mcp-config` flag (which makes sessions unresumable in Claude Code 2.1.x).

## Troubleshooting

### "Credit balance is too low"

The container is picking up `ANTHROPIC_API_KEY` from the shared `.env` instead of using OAuth.
Check `docker-compose.ai.yml` has `ANTHROPIC_API_KEY=` (empty) in the environment block.

### "--dangerously-skip-permissions cannot be used with root"

The container is running as root. The Dockerfile must have `USER bede` before `ENTRYPOINT`.

### "No conversation found with session ID: ..."

Stale session from a previous container run. Send `/reset` on Telegram to clear it.

### Bede stops responding after weeks

OAuth token has expired. Run the re-auth one-liner above from your Mac.

### OAuth callback says "this site can't be reached"

Your browser resolved `mcp.YOUR_DOMAIN` via external DNS instead of AdGuard. This happens if your machine isn't using AdGuard as its DNS server, and your public DNS has a stale or incorrect record for that subdomain (e.g. pointing to `127.0.0.1`).

**Quick fix** — add a hosts entry on your Mac:
```bash
sudo sh -c "echo '192.168.1.SERVER_IP mcp.YOUR_DOMAIN' >> /etc/hosts"
```

**Proper fix** — either remove the public DNS record for `mcp.YOUR_DOMAIN` in Gandi (the wildcard `*.YOUR_DOMAIN` entry in AdGuard handles local resolution), or make sure your Mac uses AdGuard (`SERVER_IP`) as its DNS server.

### workspace-mcp not connecting

Check workspace-mcp logs: `docker compose -f docker-compose.ai.yml logs workspace-mcp`

If OAuth tokens are missing or expired, repeat the OAuth browser flow (step 3 above).

## Phases

| Phase | Status | Description |
|---|---|---|
| 1 | ✅ Done | Docker container, Telegram bot, Claude Code integration |
| 2 | ✅ Done | Obsidian vault via git, Google Workspace MCP (Gmail, Calendar, Tasks) |
| 3 | Planned | Scheduled briefings via supercronic cron jobs |

See `docs/bede-assistant-plan.md` for the full build plan.
