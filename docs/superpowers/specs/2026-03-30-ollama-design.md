# Ollama + Open WebUI — Design Spec

**Date:** 2026-03-30
**Status:** Approved
**Depends on:** `feature/openclaw-docker` must be merged first — that branch restructures the Makefile and compose file conventions this spec builds on.

---

## Overview

Add Ollama (local LLM inference server) and Open WebUI (chat UI) to the home server stack as a new `docker-compose.ai.yml` compose file. The stack runs CPU-only on ~16GB RAM; target models are 7B and under (starting with `llama3.2:3b`).

---

## Architecture

### File layout

A new `docker-compose.ai.yml` is added alongside the existing four compose files. It follows the same conventions: bind-mount data to `./data/`, join the shared `homeserver` network, expose services via Traefik labels.

### Services

#### `ollama`
- Image: `ollama/ollama:latest`
- `container_name: ollama`
- Restart: `unless-stopped`
- Exposes port `11434` internally only (`expose: ["11434"]`, no host port binding)
- Volume: `./data/ollama:/root/.ollama`
- Environment (no inline defaults — all defined in `.env`):
  - `OLLAMA_HOST: 0.0.0.0:11434` — **required** to bind to all interfaces; Ollama's default is `127.0.0.1:11434` which is unreachable from other containers even when `expose` is declared. Without this, Open WebUI and n8n cannot connect.
  - `OLLAMA_KEEP_ALIVE` — from `.env`
  - `OLLAMA_NUM_PARALLEL` — from `.env`
  - `OLLAMA_MAX_LOADED_MODELS` — from `.env`
- Healthcheck:
  ```yaml
  test: ["CMD", "curl", "-f", "http://localhost:11434/"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
  ```
  `curl` is available in the Ubuntu-based `ollama/ollama` image. `start_period: 30s` prevents premature unhealthy status during slow cold-start on CPU-only hardware.

#### `ollama-init`
- Image: `ollama/ollama:latest`
- `container_name: ollama-init`
- Restart: `"no"`
- **Must join `homeserver` network** (unlike `n8n-init`, which only writes to a volume — `ollama-init` makes a live HTTP call to `http://ollama:11434` and will fail DNS resolution if not on the shared network)
- Depends on `ollama` (condition: `service_healthy`)
- Volume: `./data/ollama:/root/.ollama` — shares model storage with `ollama`
- Environment: `OLLAMA_HOST: http://ollama:11434` — this is the **client-side** env var used by the Ollama CLI to locate the server (note: includes scheme, unlike the server-side bind address)
- Command: `ollama pull llama3.2:3b` — `ollama pull` is idempotent; exits 0 immediately if the model is already present
- Networks: `- homeserver`

#### `open-webui`
- Image: `ghcr.io/open-webui/open-webui:latest`
- `container_name: open-webui`
- Restart: `unless-stopped`
- Exposes port `8080` internally only
- Volume: `./data/open-webui:/app/backend/data`
- Environment: `OLLAMA_BASE_URL: http://ollama:11434`
- Depends on `ollama` (condition: `service_healthy`)
- Traefik labels: routes `chat.${DOMAIN}` → port 8080, `admin-secure-no-ratelimit` middleware
- Networks: `- homeserver`

### Network

Each service declares `networks: - homeserver`. The file ends with:
```yaml
networks:
  homeserver:
    driver: bridge
```
This matches the pattern in every other compose file (not `external: true`). When multiple compose files are combined with `-f`, Docker Compose merges matching network definitions — no pre-creation step required.

This allows:
- Open WebUI to reach Ollama at `http://ollama:11434`
- n8n to reach Ollama at `http://ollama:11434` for workflow automation

Ollama is not exposed externally. For direct API access from the dev machine, connect via WireGuard VPN, then use `docker exec -it ollama ollama list` on the server, or call the API through Open WebUI's backend.

---

## Security

**Open WebUI** uses `admin-secure-no-ratelimit` middleware — same as AdGuard Home and Homepage. Open WebUI's chat interface makes 10+ rapid sequential API calls per page load and per streaming response; the `admin-secure` rate limit (10 req/min, burst 5) would cause degraded UX. `admin-secure-no-ratelimit` provides:
- IP whitelist: RFC1918 only (LAN + VPN)
- Security headers (HSTS, XSS protection, frame deny, content-type nosniff)
- No rate limiting

**Ollama API** has no Traefik exposure and no host port binding. Access is Docker-internal only.

---

## Environment Variables

Add to `.env.example` (no inline defaults in compose files):

```bash
# Ollama Configuration
# How long to keep a model loaded in memory after the last request (0 = unload immediately)
OLLAMA_KEEP_ALIVE=24h
# Max concurrent requests processed simultaneously (1 = sequential, safe for 16GB RAM)
OLLAMA_NUM_PARALLEL=1
# Max number of models loaded in memory at once (1 recommended for 16GB RAM CPU-only)
OLLAMA_MAX_LOADED_MODELS=1
```

All three variables must be added to `.env` before `make validate` will pass, as the compose file uses bare `${VAR}` references with no fallback.

---

## Data Persistence

| Path | Purpose |
|---|---|
| `./data/ollama` | Ollama models and runtime data |
| `./data/open-webui` | Open WebUI conversation history and user data |

Note: `llama3.2:3b` is approximately 2GB on disk. Allocate at least 20GB free in `./data/ollama` if planning to pull additional models via the UI.

---

## Startup behaviour

On first `make start`:
1. `ollama` starts and passes its healthcheck (API up, ~30s cold start on CPU-only hardware)
2. `ollama-init` starts and runs `ollama pull llama3.2:3b` — approximately 2GB download, may take several minutes
3. `open-webui` starts as soon as `ollama` is healthy (step 1), before the model pull completes

**Expected UX:** Open WebUI will be accessible at `https://chat.${DOMAIN}` before the model is ready. Users who attempt a chat during the model pull will receive an error or loading state from Open WebUI. This is acceptable — the model will be available once the pull completes.

**Subsequent `make start`** (after normal shutdown): `ollama-init` is in `Exited (0)` state. `docker compose up -d` does not re-create exited containers unless the image or config has changed, so the pull does not re-run. This is the desired idempotent behaviour.

**`make restart`** (`docker compose restart`): only restarts already-running containers; `ollama-init` (exited) is not touched. Correct.

**After `make purge` + `make start`**: `./data/ollama` has been deleted; `ollama-init` container has been removed by `docker compose down -v`. On `make start`, the container is re-created and `ollama pull` runs again to re-download the model.

---

## Makefile Changes

### `COMPOSE` variable
Add `docker-compose.ai.yml` to `COMPOSE` only (not `COMPOSE_CORE`). AI services are application-layer, not infrastructure:
```makefile
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.ai.yml
```

This automatically propagates to all targets that use `$(COMPOSE)`: `start`, `stop`, `restart`, `status`, `logs`, `update`, `validate`, `pull`, `clean`, `purge`.

### `.PHONY` additions
Add to the existing `.PHONY` line that contains `logs-n8n logs-homepage`:
```
logs-ollama logs-open-webui
```

### New log targets
```makefile
logs-ollama:
	@$(COMPOSE) logs -f ollama

logs-open-webui:
	@$(COMPOSE) logs -f open-webui
```

### `help` target additions
In the "Logs & Debugging" section:
```
  make logs-ollama        - Show Ollama LLM server logs
  make logs-open-webui    - Show Open WebUI chat interface logs
```

### `purge` warning message
Add two lines to the purge warning listing:
```
  - Ollama model data (WARNING: models are large, re-download required)
  - Open WebUI conversation history and user data
```

---

## Dashboard Integration

Add to `config/homepage/services-template.yaml` under a new "AI" section:

```yaml
- Ollama:
    icon: ollama.png
    href: ""
    description: Local LLM inference server
    container: ollama
    server: my-docker
    showStats: true

- Open WebUI:
    icon: open-webui.png
    href: https://chat.{{HOMEPAGE_VAR_DOMAIN}}
    description: Local AI chat interface
    container: open-webui
    server: my-docker
    showStats: true
```

`container:` values match `container_name:` in the compose file (`ollama` and `open-webui`). Note: confirm that `ollama.png` and `open-webui.png` exist in the Homepage dashboard-icons library before finalising; if not, fall back to generic icons (e.g., `mdi-brain` and `mdi-chat`).

---

## SERVICES.md

- Move Ollama from the planned services checklist to the Running section
- Add Open WebUI as a new running service:
  - Purpose: Local AI chat interface (ChatGPT alternative)
  - Access: `https://chat.${DOMAIN}`
  - Authentication: IP-restricted (LAN / VPN only)

---

## Constraints & Notes

- **CPU-only:** No GPU passthrough configured. GPU can be added later by appending a `deploy.resources.reservations.devices` block to the `ollama` service (no image change needed — `ollama/ollama:latest` bundles CUDA backends).
- **n8n integration:** n8n's HTTP Request node or Ollama community node can POST to `http://ollama:11434/api/generate` on the shared Docker network. Ollama v0.18+ supports structured JSON output constrained by a schema — useful for automation workflows.
- **Model storage:** Running `make validate` will fail if the new env vars are not yet in `.env`. Add them from `.env.example` before validating.
