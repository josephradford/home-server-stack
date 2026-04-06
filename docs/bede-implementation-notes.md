# Bede Implementation Notes

Lessons learned building the Bede AI assistant (Phases 1 & 2). Intended as a
reference for Phase 3 work and anyone picking this up fresh.

---

## Claude Code session persistence

**Problem:** Every message started a fresh conversation — no memory of previous turns.

There were two separate root causes, fixed independently:

### 1. `--mcp-config` makes sessions unresumable (Claude Code 2.1.x)

Passing `--mcp-config <file>` to `claude -p` causes Claude Code to generate a
new session ID on every invocation, making `--resume` impossible. This is a
known bug in Claude Code 2.1.x.

**Fix:** Remove `--mcp-config` entirely. Instead, place `.mcp.json` in the
working directory (`/app`). Claude Code auto-discovers it without breaking
session continuity.

### 2. `~/.claude/` owned by root

When Docker starts a container and a bind mount's parent directory doesn't
exist on the host, Docker creates it as root. The `bede` user (uid 1000) then
can't write session state to `~/.claude/`.

**Fix:** Pre-create `/home/bede/.claude` in the Dockerfile `RUN useradd ...`
step with `chown bede:bede`. This ensures the directory exists with the right
ownership before the bind mount is applied.

```dockerfile
RUN useradd --system --create-home --uid 1000 --shell /bin/bash bede && \
    mkdir -p /home/bede/.ssh /home/bede/.claude && \
    chmod 700 /home/bede/.ssh && \
    chown -R bede:bede /home/bede/.ssh /home/bede/.claude
```

---

## MCP configuration

`mcpServers` in `~/.claude/settings.json` is **not** supported by Claude Code.
The only working approaches are:

- `.mcp.json` in the working directory — auto-discovered, sessions resumable
- `--mcp-config <file>` flag — works but breaks session resumability (see above)

Use `.mcp.json` in the workdir.

---

## Docker named volumes vs bind mounts

Named Docker volumes are created by the Docker daemon as root at container
start time. If the container runs as a non-root user, it cannot write to them.

This bit us twice:
1. `~/.claude/` — fixed by pre-creating in Dockerfile (see above)
2. `/vault` (Obsidian vault) — the `bede-vault` named volume was created as
   root, so `git clone` failed with "Permission denied"

**Fix for `/vault`:** Switch to a bind mount under `./data/bede/vault/`, which
is created by the Makefile as the host user before Docker starts:

```makefile
bede-start: env-check
    @mkdir -p data/bede/vault
    @$(COMPOSE_AI) up -d
```

**Rule of thumb:** For any non-root container that needs to write to a volume,
use a bind mount under `./data/` and `mkdir -p` it before `compose up`.

---

## `make bede-restart` vs `make bede-build`

`make bede-restart` (and `bede-start`) reuse the existing Docker image. Code
changes to Python files, scripts, or configs inside the image are **not picked
up** without a rebuild.

Always run `make bede-build` before `make bede-start` when deploying code
changes. The Makefile does not do this automatically.

---

## Google Workspace MCP OAuth

### Credentials are per-account

workspace-mcp stores OAuth tokens in `GOOGLE_MCP_CREDENTIALS_DIR` as
`{email}.json`. If Bede's Claude account (ai.joeradford) has Google connectors
attached in the claude.ai UI, those will be used instead of workspace-mcp —
and they'll authenticate as a different Google account (joeradford@gmail.com
vs whatever ai.joeradford is linked to).

**Fix:** Remove Google connectors from the claude.ai account so all Google
access goes exclusively through workspace-mcp.

### OAuth callback DNS

The workspace-mcp OAuth callback (`mcp.{DOMAIN}/oauth2callback`) must resolve
to the server IP, not a public DNS record. If your domain's public DNS has a
stale record for that subdomain (e.g. `mcp.example.com → 127.0.0.1` from
a previous setup), the browser will follow public DNS instead of AdGuard.

**Quick fix** — add a hosts entry on the client machine:
```bash
sudo sh -c "echo '192.168.1.SERVER_IP mcp.DOMAIN' >> /etc/hosts"
```

**Proper fix** — remove the conflicting public DNS record (Gandi or equivalent).
AdGuard's wildcard `*.DOMAIN → SERVER_IP` rewrite handles local resolution.

---

## Container restart loop on vault clone failure

If `git clone` fails (e.g. bad credentials, missing permissions) and
`set -e` is active in `entrypoint.sh`, the container exits and Docker restarts
it — creating a fast restart loop. The vault directory from the failed partial
clone persists on the bind mount across restarts, but since it has no `.git`
folder the entrypoint keeps retrying `git clone`.

Once credentials are fixed, the clone will succeed on the next restart and the
loop stops. The container stabilises automatically — no manual cleanup needed
unless there are leftover partial files.

---

## GitHub fine-grained PATs for vault access

Fine-grained PATs require explicit repository selection. Creating a PAT with
"Read access to code and metadata" is sufficient for `git clone`, but the PAT
must have `josephradford/obs-vault` (or "All repositories") in its repository
access list.

The error GitHub returns for an insufficiently-scoped PAT is:
```
remote: Write access to repository not granted.
fatal: unable to access '...': The requested URL returned error: 403
```

This is misleading — it's an authorisation failure on read, not a write
attempt.

---

## Orphaned containers

When services are removed from a compose file (e.g. ollama, open-webui,
openclaw-gateway), the containers are not automatically stopped or removed.
They continue running until explicitly stopped:

```bash
docker stop ollama open-webui openclaw-gateway
docker rm ollama open-webui openclaw-gateway
```

Docker will warn about orphan containers on subsequent `compose up` runs with:
```
Found orphan containers ([...]) for this project.
```
