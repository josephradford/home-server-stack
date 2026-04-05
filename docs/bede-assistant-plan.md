# Bede — Personal AI Assistant

A personal assistant accessible via Telegram, running in Docker on the home server, powered by Claude Code CLI (`claude -p`). Handles calendar, email, Obsidian vault queries, and scheduled briefings.

---

## Architecture

```
Telegram message
      ↓
  bot.py (long-polling)
      ↓
  claude -p "message" [--resume session_id] --dangerously-skip-permissions
      ↓
  Claude Code (CLAUDE.md persona + MCP tools + vault filesystem)
      ↓
Telegram reply
```

### Docker layout

```
docker-compose.ai.yml
└── bede (single container)
    ├── supervisord
    │   ├── bot.py (Telegram long-polling, always running)
    │   └── supercronic (scheduled briefings)
    ├── claude CLI (npm global install)
    ├── git + Obsidian vault (volume, cloned on start)
    └── ~/.claude/.credentials.json (bind-mount from host)
```

MCP servers added in Phase 2 as sidecar containers on the internal Docker network.

---

## File Structure

```
bede/
├── Dockerfile
├── docker-compose.ai.yml         # merged into home-server-stack or standalone
├── bot.py                        # Telegram long-polling + claude -p subprocess
├── CLAUDE.md                     # Bede persona, context, behavioural rules
├── mcp.json                      # MCP server config (Phase 2+)
├── requirements.txt              # python-telegram-bot, python-dotenv
├── crontab                       # supercronic schedule for briefings
├── supervisord.conf              # manages bot.py + supercronic
├── scripts/
│   ├── entrypoint.sh             # clone/pull vault, then start supervisord
│   └── briefing.sh               # cron entry: claude -p | send to Telegram
└── .env                          # TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID, VAULT_REPO
```

---

## Key Design Decisions

### `claude -p` over Channels plugin

| | Channels Plugin | `claude -p` (chosen) |
|---|---|---|
| Context | Grows forever in one session | Fresh per conversation, opt-in continuity |
| Session reset | No built-in periodic reset | Clean fresh start each message |
| Scheduling | N/A | Cron or bot.py |
| ToS clarity | Fine | Fine (confirmed by Boris Cherny) |

Growing context is a real quality problem for a persistent personal assistant. `claude -p` gives clean per-conversation context with opt-in continuity via `--resume`.

### Multi-turn session tracking

- Each new conversation gets a fresh `claude -p` call
- Session ID captured from `--output-format json` stdout
- Follow-up messages within a 10-minute timeout window use `--resume <session_id>`
- After timeout, next message starts a fresh session

### Permissions

Run with `--dangerously-skip-permissions` — no terminal is available to approve prompts. Mitigated by clear boundaries defined in `CLAUDE.md`.

### Security

- `.env` holds bot token and your Telegram user ID
- `bot.py` checks every incoming message against `ALLOWED_USER_ID` before any `claude -p` call — not just on startup

### OAuth credentials in Docker

- `~/.claude/.credentials.json` bind-mounted from host into container
- When tokens expire, re-auth one-liner from Mac updates the host file; no container restart needed:
  ```bash
  security find-generic-password -s "Claude Code-credentials" -w | ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"
  ```
- `bot.py` detects auth failures from `claude -p` stderr and sends a Telegram alert with the re-auth command

### Two processes via supervisord

`bot.py` (always running) + supercronic (cron daemon) managed by supervisord to avoid PID 1 issues.

### Obsidian vault via git (not GitHub MCP)

The GitHub MCP is for code repos (PRs, issues). For the vault:
- `entrypoint.sh` does `git clone $VAULT_REPO /vault` on first start (or `git pull` if volume already populated)
- `bot.py` and `briefing.sh` run `git -C /vault pull` before invoking claude
- Claude reads/writes via its built-in filesystem tools

---

## Known Issues / Lessons Learned

### `claude auth login` broken over SSH

The interactive input prompt doesn't handle stdin over SSH sessions correctly. Confirmed open bug on the Claude Code GitHub repo ([#41485](https://github.com/anthropics/claude-code/issues/41485)).

**Workaround:** Copy credentials directly from Mac Keychain:
```bash
# Run from Mac
security find-generic-password -s "Claude Code-credentials" -w | \
  ssh user@SERVER_IP "cat > ~/.claude/.credentials.json"
```

### Cowork scheduled tasks — macOS/Windows only

Cowork scheduled tasks would cover briefings natively but don't run on Linux. `cron + claude -p` is the equivalent approach on Ubuntu.

### ToS status

Personal CLI wrappers using `claude -p` are explicitly permitted. Confirmed by Boris Cherny (Claude Code creator). The February 2026 ToS clarification targeted third-party harnesses routing other users' subscriptions — not personal automation.

### `--dangerously-skip-permissions` blocked when running as root

Claude Code refuses `--dangerously-skip-permissions` if the process runs as root/sudo. Docker containers run as root by default.

**Fix:** Use a non-root user. `node:20-slim` ships a `node` user at UID 1000 — use `USER node` in the Dockerfile rather than creating a new user (`useradd` will fail with exit code 4 because UID 1000 is already taken).

### supervisord pidfile not writable as non-root

Supervisord defaults to writing its pidfile at `/var/run/supervisord.pid`, which requires root.

**Fix:** Set `pidfile=/tmp/supervisord.pid` in `supervisord.conf`.

### ANTHROPIC_API_KEY in shared .env overrides OAuth credentials

Claude Code prioritises `ANTHROPIC_API_KEY` over the credentials file. If the shared `.env` contains an API key with no balance, every `claude -p` call will fail with "Credit balance is too low" even though valid OAuth credentials are bind-mounted.

**Fix:** Explicitly blank the key in the bede service's `environment` block in `docker-compose.ai.yml`:
```yaml
environment:
  - ANTHROPIC_API_KEY=  # blank out shared .env value — bede uses OAuth
```

### stdin warning from claude CLI

Running `claude -p` without explicit stdin produces: _"Warning: no stdin data received in 3s"_.

**Fix:** Pass `stdin=subprocess.DEVNULL` in Python subprocess calls, and `< /dev/null` in shell scripts.

---

## Build Phases

### Phase 1 — Docker + Telegram bot

1. **Dockerfile**: Node.js base + `npm install -g @anthropic-ai/claude-code` + Python + pip deps + supercronic + supervisord
2. **`bot.py`**: Telegram long-polling → `claude -p` subprocess → session tracking → reply. Detect auth failures, send Telegram alert.
3. **`CLAUDE.md`**: Bede persona, your context, vault path, safety rules
4. **Credentials**: Host bind-mount of `~/.claude/.credentials.json`
5. **No vault yet** — validate the bot works end-to-end first

### Phase 2 — Obsidian vault + MCP connectors

1. **Vault access**: `entrypoint.sh` clones the vault repo via SSH key or HTTPS PAT. `git pull` before each claude invocation.
2. **Gmail + Calendar MCP**: Add `mcp-google-calendar` and `mcp-gmail` sidecar containers. Handle Google OAuth on the laptop, persist tokens in a named volume.
3. Wire `--mcp-config mcp.json` into every `claude -p` call.

### Phase 3 — Scheduled briefings

Cron via supercronic inside the container:

```
# crontab
0 7 * * *     /app/scripts/briefing.sh morning
0 18 * * 1-5  /app/scripts/briefing.sh evening
0 9 * * 0     /app/scripts/briefing.sh weekly
```

`briefing.sh` calls `claude -p` with a briefing prompt and POSTs the output to Telegram via `curl`. No long-polling needed for outbound-only messages.

---

## Environment Variables

```env
# Telegram
TELEGRAM_BOT_TOKEN=...
ALLOWED_USER_ID=...

# Obsidian vault
VAULT_REPO=git@github.com:you/obsidian-vault.git
# or VAULT_REPO=https://<PAT>@github.com/you/obsidian-vault.git

# Claude (credentials come from bind-mount, not env)
```

Google OAuth credentials for MCP servers stored in named volumes, not env vars.

---

## Open Problems

1. **Google OAuth for MCP servers** — separate browser flow from Claude Code auth. Needs a plan before Phase 2.
2. **Vault SSH key in container** — needs to be bind-mounted or passed as a secret, not baked into the image.
3. **Token expiry monitoring** — detect `claude -p` auth failures and alert via Telegram before the assistant goes silent.

---

## Documentation Checklist

Before closing out the implementation, update the following at a minimum:

- [ ] `README.md` — add Bede to the services overview
- [ ] `SERVICES.md` — add Bede entry with domain, port, and description
- [ ] `docs/ARCHITECTURE.md` — add Bede to the architecture diagram and service descriptions
- [ ] `bede/README.md` — keep in sync with any Dockerfile / design changes
- [ ] `.env.example` — ensure all Bede env vars are documented with descriptions
- [ ] This plan doc — update the Docker layout diagram and any stale phase descriptions

---

## References

- [Claude Code headless docs](https://docs.anthropic.com/en/docs/claude-code/headless-mode)
- [Claude Code legal and compliance](https://docs.anthropic.com/en/docs/claude-code/legal-and-compliance)
- [Claude Code SSH auth bug #41485](https://github.com/anthropics/claude-code/issues/41485)
- [Supercronic (container-friendly cron)](https://github.com/aptible/supercronic)
