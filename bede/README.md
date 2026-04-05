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
VAULT_REPO=           # leave blank until Phase 2
SESSION_TIMEOUT_MINUTES=10
```

**2. Sync Claude OAuth credentials from Mac to server:**
```bash
security find-generic-password -s "Claude Code-credentials" -w | \
  ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"
```

**3. Build and start:**
```bash
docker compose -f docker-compose.ai.yml up -d --build
docker compose -f docker-compose.ai.yml logs -f bede
```

**4. Create your persona file** — `bede/CLAUDE.md` is gitignored (it's personal). Copy the example and fill in your details:
```bash
cp bede/CLAUDE.md.example bede/CLAUDE.md
# Edit bede/CLAUDE.md — set your name, location, timezone, role, interests
```

## Day-to-day Commands

```bash
# Start
docker compose -f docker-compose.ai.yml up -d

# Stop
docker compose -f docker-compose.ai.yml down

# View logs
docker compose -f docker-compose.ai.yml logs -f bede

# Rebuild after code changes
docker compose -f docker-compose.ai.yml up -d --build
```

## Telegram Commands

- `/start` — greeting and available commands
- `/reset` — clear the current session (start a fresh conversation)

## Re-authenticating (when OAuth token expires)

Tokens last weeks to months. When Bede stops responding or you get an auth error, run from your Mac:

```bash
security find-generic-password -s "Claude Code-credentials" -w | \
  ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"
```

No container restart needed — the credentials file is bind-mounted live.

## Architecture

```
docker-compose.ai.yml
└── bede container
    ├── supervisord (PID 1)
    │   ├── bot.py          — Telegram long-polling
    │   └── supercronic     — scheduled briefings (Phase 3)
    ├── claude CLI          — npm install -g @anthropic-ai/claude-code
    └── ~/.claude/.credentials.json  ← bind-mounted from host
```

## Troubleshooting

### "Credit balance is too low"

The container is picking up `ANTHROPIC_API_KEY` from the shared `.env` instead of using OAuth.
Check `docker-compose.ai.yml` has `ANTHROPIC_API_KEY=` (empty) in the environment block.

### "--dangerously-skip-permissions cannot be used with root"

The container is running as root. The Dockerfile must have `USER node` before `ENTRYPOINT`.

### "No conversation found with session ID: ..."

Stale session from a previous container run. Send `/reset` on Telegram to clear it.

### Bede stops responding after weeks

OAuth token has expired. Run the re-auth one-liner above from your Mac.

## Phases

| Phase | Status | Description |
|---|---|---|
| 1 | ✅ Done | Docker container, Telegram bot, Claude Code integration |
| 2 | Planned | Obsidian vault via git, Gmail + Calendar MCP sidecars |
| 3 | Planned | Scheduled briefings via supercronic cron jobs |

See `docs/bede-assistant-plan.md` for the full build plan.
