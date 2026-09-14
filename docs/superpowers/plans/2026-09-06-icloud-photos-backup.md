# iCloud Photos Backup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two `icloudpd` containers that continuously back up two separate iCloud photo libraries to an external drive, surface them on the Homepage dashboard with a health tile, and notify by email when re-authentication is needed.

**Architecture:** A new `docker-compose.photos.yml` defines two `icloudpd/icloudpd` containers (`icloudpd-a`, `icloudpd-b`) running `--watch-with-interval`. Each serves its own web UI (port 8080) for password/2FA entry, routed via Traefik behind the existing `admin-secure` IP allowlist. A shell wrapper in each container's `command` refuses to run unless a sentinel file on the external drive matches an expected ID (guards against unmounted / wrong drive). A new `homepage-api` endpoint reads Docker state + recent container logs and classifies each backup's health for a Homepage `customapi` tile. No Prometheus/Alertmanager changes.

**Tech Stack:** Docker Compose, Traefik v3 (file-provider TLS), `icloudpd/icloudpd:1.32.3`, Flask (homepage-api, Python 3.11, stdlib `http.client` over the Docker Unix socket), pytest.

**Spec:** `docs/superpowers/specs/2026-09-06-icloud-photos-backup-design.md`

## Global Constraints

- **No identifying data in committed code.** Apple IDs, the operator's/family names, drive paths, drive IDs, SMTP creds, and display labels live only in `.env`. `.env.example` ships generic placeholders only. Container names are `icloudpd-a` / `icloudpd-b`.
- **The Apple ID password must never appear in the repo or in `.env`.** Use `--password-provider webui` so it is entered in the browser and persisted only in the mounted cookie directory.
- **Never add `--auto-delete` or `--delete-after-download`** to the icloudpd command. The backup is download-only; deletions in iCloud must not propagate.
- **Pinned image:** `icloudpd/icloudpd:1.32.3`.
- **icloudpd web UI port:** `8080` (active only when `webui` is an MFA and/or password provider).
- **Traefik pattern for admin UIs:** `entrypoints=websecure`, `tls=true` (file-provider wildcard cert — no `certresolver`), middleware `admin-secure`. Follow the exact label shape already used by `prometheus` in `docker-compose.monitoring.yml`.
- **homepage-api internal URL** used by Homepage widgets is `http://homepage-api:5000` (the container listens on 5000 via gunicorn; ignore the `5200` in `app.py`'s `__main__`).
- **Data persistence:** bind mounts under `./data/` only, matching the rest of the stack.
- Follow the "Adding a New Service" checklist in `CLAUDE.md` (compose labels, `.env.example`, Homepage entry, `SERVICES.md`, validate).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `docker-compose.photos.yml` (create) | The two `icloudpd` service definitions, via a YAML anchor for the shared body. |
| `.env.example` (modify) | Generic placeholder block for all new variables. |
| `Makefile` (modify) | Add the new compose file to `COMPOSE`; add `logs-icloudpd` target; update the header comment. |
| `homepage-api/app.py` (modify) | `_docker_logs(name)` raw-stream helper + `/api/icloudpd/status/<name>` route + classifier. |
| `homepage-api/tests/test_app.py` (modify) | Tests for the classifier and route. |
| `config/homepage/services-template.yaml` (modify) | New **Backups** group with two entries + `customapi` widgets. |
| `docker-compose.dashboard.yml` (modify) | Pass `HOMEPAGE_VAR_ICLOUD_A_LABEL` / `_B_LABEL` to the homepage container. |
| `docs/icloud-photos-backup.md` (create) | Operator guide: drive/fstab setup, first-run auth, re-auth routine, drive replacement, protection scope, dashboard status meaning. |
| `SERVICES.md` (modify) | Two service entries + quick-reference rows. |
| `README.md` (modify) | One-line mention alongside other services. |

---

## Task 1: Compose file, environment, Makefile wiring

**Files:**
- Create: `docker-compose.photos.yml`
- Modify: `.env.example` (append new block at end)
- Modify: `Makefile:14-28` (header comment + `COMPOSE`), `Makefile:~338` (new `logs-icloudpd` target near `logs-owntracks`)
- Create (empty, git-tracked dirs via `.gitkeep`): `data/icloudpd/a/cookies/.gitkeep`, `data/icloudpd/b/cookies/.gitkeep`

**Interfaces:**
- Produces: containers named `icloudpd-a`, `icloudpd-b` on the `homeserver` network; Traefik routers `icloud-a`, `icloud-b`; env var names consumed by Task 3 (`ICLOUD_A_LABEL`, `ICLOUD_B_LABEL`) and by the operator docs in Task 4.

- [ ] **Step 1: Write `docker-compose.photos.yml`**

```yaml
# iCloud Photos backup — two icloudpd containers, one per Apple account.
# See docs/icloud-photos-backup.md for setup. All identifying values are in .env.
#
# The Apple ID password is entered via each container's web UI (never stored in
# .env or the repo) and persisted only in ./data/icloudpd/<x>/cookies.

x-icloudpd-common: &icloudpd-common
  image: icloudpd/icloudpd:1.32.3
  restart: unless-stopped
  networks:
    - homeserver
  environment:
    TZ: ${TZ:-Australia/Sydney}
    ICLOUD_BACKUP_DRIVE_ID: ${ICLOUD_BACKUP_DRIVE_ID}

services:
  icloudpd-a:
    <<: *icloudpd-common
    container_name: icloudpd-a
    volumes:
      - ${ICLOUD_BACKUP_ROOT}:/drive
      - ./data/icloudpd/a/cookies:/cookies
    command:
      - /bin/sh
      - -c
      - |
        if [ "$$(cat /drive/.backup-drive 2>/dev/null)" != "$$ICLOUD_BACKUP_DRIVE_ID" ]; then
          echo "backup drive not mounted or wrong drive"; sleep 3600; exit 1
        fi
        exec icloudpd \
          --directory /drive/${ICLOUD_A_SUBDIR} \
          --username ${ICLOUD_A_USERNAME} \
          --cookie-directory /cookies \
          --watch-with-interval ${ICLOUD_A_INTERVAL:-21600} \
          --folder-structure "${ICLOUD_FOLDER_STRUCTURE:-{:%Y/%m}}" \
          --password-provider webui \
          --mfa-provider webui \
          --smtp-host ${ICLOUD_SMTP_HOST} \
          --smtp-port ${ICLOUD_SMTP_PORT:-587} \
          --smtp-username ${ICLOUD_SMTP_USERNAME} \
          --smtp-password ${ICLOUD_SMTP_PASSWORD} \
          --notification-email ${ICLOUD_NOTIFICATION_EMAIL} \
          --no-progress-bar
    healthcheck:
      test: ["CMD-SHELL", "test \"$(cat /drive/.backup-drive 2>/dev/null)\" = \"$ICLOUD_BACKUP_DRIVE_ID\""]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.icloud-a.rule=Host(`icloud-a.${DOMAIN}`)"
      - "traefik.http.routers.icloud-a.entrypoints=websecure"
      - "traefik.http.routers.icloud-a.tls=true"
      - "traefik.http.services.icloud-a.loadbalancer.server.port=8080"
      - "traefik.http.routers.icloud-a.middlewares=admin-secure"

  icloudpd-b:
    <<: *icloudpd-common
    container_name: icloudpd-b
    volumes:
      - ${ICLOUD_BACKUP_ROOT}:/drive
      - ./data/icloudpd/b/cookies:/cookies
    command:
      - /bin/sh
      - -c
      - |
        if [ "$$(cat /drive/.backup-drive 2>/dev/null)" != "$$ICLOUD_BACKUP_DRIVE_ID" ]; then
          echo "backup drive not mounted or wrong drive"; sleep 3600; exit 1
        fi
        sleep ${ICLOUD_B_START_DELAY:-1800}
        exec icloudpd \
          --directory /drive/${ICLOUD_B_SUBDIR} \
          --username ${ICLOUD_B_USERNAME} \
          --cookie-directory /cookies \
          --watch-with-interval ${ICLOUD_B_INTERVAL:-23400} \
          --folder-structure "${ICLOUD_FOLDER_STRUCTURE:-{:%Y/%m}}" \
          --password-provider webui \
          --mfa-provider webui \
          --smtp-host ${ICLOUD_SMTP_HOST} \
          --smtp-port ${ICLOUD_SMTP_PORT:-587} \
          --smtp-username ${ICLOUD_SMTP_USERNAME} \
          --smtp-password ${ICLOUD_SMTP_PASSWORD} \
          --notification-email ${ICLOUD_NOTIFICATION_EMAIL} \
          --no-progress-bar
    healthcheck:
      test: ["CMD-SHELL", "test \"$(cat /drive/.backup-drive 2>/dev/null)\" = \"$ICLOUD_BACKUP_DRIVE_ID\""]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.icloud-b.rule=Host(`icloud-b.${DOMAIN}`)"
      - "traefik.http.routers.icloud-b.entrypoints=websecure"
      - "traefik.http.routers.icloud-b.tls=true"
      - "traefik.http.services.icloud-b.loadbalancer.server.port=8080"
      - "traefik.http.routers.icloud-b.middlewares=admin-secure"

networks:
  homeserver:
    driver: bridge
```

Notes for the implementer:
- `$$` escapes a literal `$` for Docker Compose so the shell (not Compose) expands `ICLOUD_BACKUP_DRIVE_ID` inside the `sh -c` script; `${ICLOUD_A_SUBDIR}` etc. with a single `$` are intentionally expanded by Compose from `.env`.
- The healthcheck `test` string uses single `$` because it is passed straight to the container shell at runtime, not through Compose interpolation — Compose leaves `CMD-SHELL` array items with `$VAR` alone only if written as `$$VAR`. Write it as `$$ICLOUD_BACKUP_DRIVE_ID` and `$$(cat ...)` in the file; verify with `docker compose ... config` that the rendered output shows a single `$`.
- If `docker compose config` reports the web UI needs a different flag or the SMTP flag names differ for `1.32.3`, run `docker run --rm icloudpd/icloudpd:1.32.3 icloudpd --help` and correct the flags. Do not guess — match `--help` output.

- [ ] **Step 2: Verify the compose file renders**

Run: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.location.yml -f docker-compose.photos.yml config --quiet`
Expected: exits 0, no error. (Populate the new `.env` vars first — Step 4 — or export dummy values for the check.)

- [ ] **Step 3: Add the `.gitkeep` files**

```bash
mkdir -p data/icloudpd/a/cookies data/icloudpd/b/cookies
touch data/icloudpd/a/cookies/.gitkeep data/icloudpd/b/cookies/.gitkeep
```

- [ ] **Step 4: Append the `.env.example` block**

Append to the end of `.env.example`:

```bash
# =============================================================================
# iCloud Photos Backup (icloudpd)
# =============================================================================
# Two containers back up two iCloud photo libraries to an external drive.
# The Apple ID PASSWORD is NOT set here — it is entered once per container in
# the web UI at https://icloud-a.${DOMAIN} / https://icloud-b.${DOMAIN}.
# See docs/icloud-photos-backup.md for full setup.

# Absolute host path where the external backup drive is mounted (see fstab setup).
ICLOUD_BACKUP_ROOT=/mnt/photos-backup
# Identity string; must equal the contents of ${ICLOUD_BACKUP_ROOT}/.backup-drive.
# Containers refuse to run unless it matches (guards against unmounted/wrong drive).
ICLOUD_BACKUP_DRIVE_ID=change-me-unique-drive-id

# Continuous sync cadence in seconds. B is offset so the two heavy passes on a
# spinning disk drift apart instead of aligning every cycle.
ICLOUD_A_INTERVAL=21600
ICLOUD_B_INTERVAL=23400
ICLOUD_B_START_DELAY=1800

# icloudpd folder layout within each account's tree.
ICLOUD_FOLDER_STRUCTURE={:%Y/%m}

# SMTP for icloudpd's "2FA expired, re-auth needed" notification email.
ICLOUD_SMTP_HOST=smtp.example.com
ICLOUD_SMTP_PORT=587
ICLOUD_SMTP_USERNAME=alerts@example.com
ICLOUD_SMTP_PASSWORD=app_password_here
ICLOUD_NOTIFICATION_EMAIL=you@example.com

# Account A
ICLOUD_A_USERNAME=appleid-a@example.com
ICLOUD_A_SUBDIR=account-a
ICLOUD_A_LABEL=Photos A

# Account B
ICLOUD_B_USERNAME=appleid-b@example.com
ICLOUD_B_SUBDIR=account-b
ICLOUD_B_LABEL=Photos B
```

- [ ] **Step 5: Wire the Makefile**

In the header comment block (`Makefile:14-19`), add after the `docker-compose.location.yml` line:

```make
# - docker-compose.photos.yml: iCloud photo backup (icloudpd-a, icloudpd-b)
```

Change `COMPOSE` (`Makefile:28`) to append `-f docker-compose.photos.yml`:

```make
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.location.yml -f docker-compose.photos.yml
```

Add a logs target next to `logs-owntracks`:

```make
logs-icloudpd:
	@$(COMPOSE) logs -f icloudpd-a icloudpd-b
```

If there is a `.PHONY` list that enumerates `logs-*` targets, add `logs-icloudpd` to it.

- [ ] **Step 6: Validate**

Run: `make validate`
Expected: PASS (`$(COMPOSE) config --quiet` exits 0). Requires the new `.env` vars to exist locally; set throwaway values in `.env` if needed for the check.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.photos.yml .env.example Makefile data/icloudpd/a/cookies/.gitkeep data/icloudpd/b/cookies/.gitkeep
git commit -m "feat: add icloudpd photo backup containers"
```

---

## Task 2: homepage-api status endpoint

**Files:**
- Modify: `homepage-api/app.py` (add after the `docker_status` route, before `if __name__ == '__main__':`)
- Test: `homepage-api/tests/test_app.py` (new `TestIcloudpdStatusEndpoint` class)

**Interfaces:**
- Consumes: existing `_docker_api(path)` helper in `app.py` (GET → parsed JSON over the Docker Unix socket).
- Produces:
  - `_docker_logs(name: str, tail: int = 250) -> str` — returns recent combined stdout/stderr log text for a container, frame headers stripped.
  - `_classify_icloudpd(state: dict, health: str | None, logs: str) -> dict` — pure function returning `{"status", "statusLabel", "lastSync", "lastSyncRelative", "message"}`.
  - Route `GET /api/icloudpd/status/<name>` where `name` ∈ `{"icloudpd-a", "icloudpd-b"}`, returning that dict as JSON (HTTP 200 always; unknown/socket errors → `status: "unknown"`). Invalid `name` → HTTP 404 `{"error": "unknown container"}`.

- [ ] **Step 1: Write failing tests**

Add to `homepage-api/tests/test_app.py`:

```python
class TestIcloudpdStatusEndpoint:
    """Tests for /api/icloudpd/status/<name>"""

    def test_rejects_unknown_container_name(self, client):
        resp = client.get('/api/icloudpd/status/n8n')
        assert resp.status_code == 404

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_running_and_recent_sync_is_ok(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-06T00:00:00Z',
                      'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-06T04:15:00Z INFO Downloading 0 original photos to /drive/account-a\n"
            "2026-09-06T04:15:03Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status/icloudpd-a')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['statusLabel'] == 'OK'
        assert data['lastSync'] == '2026-09-06T04:15:03Z'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_mfa_prompt_is_auth_required(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-06T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-06T04:15:00Z INFO All photos have been downloaded\n"
            "2026-09-08T02:00:00Z ERROR Invalid authentication token, please log in\n"
            "2026-09-08T02:00:01Z INFO Waiting for MFA code via webui\n"
        )
        resp = client.get('/api/icloudpd/status/icloudpd-a')
        data = resp.get_json()
        assert data['status'] == 'auth_required'
        assert data['statusLabel'] == 'Re-auth needed'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_drive_guard_message_is_drive_missing(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-06T00:00:00Z', 'Health': {'Status': 'unhealthy'}}
        }
        mock_logs.return_value = "backup drive not mounted or wrong drive\n"
        resp = client.get('/api/icloudpd/status/icloudpd-b')
        data = resp.get_json()
        assert data['status'] == 'drive_missing'
        assert data['statusLabel'] == 'Drive not mounted'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_not_running_is_down(self, mock_api, mock_logs, client):
        mock_api.return_value = {'State': {'Status': 'exited', 'Running': False, 'Health': None}}
        mock_logs.return_value = ""
        resp = client.get('/api/icloudpd/status/icloudpd-a')
        data = resp.get_json()
        assert data['status'] == 'down'
        assert data['statusLabel'] == 'Stopped'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_in_progress_is_syncing(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-06T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-06T04:15:03Z INFO All photos have been downloaded\n"
            "2026-09-06T10:00:00Z INFO Downloading 240 original photos to /drive/account-a\n"
        )
        resp = client.get('/api/icloudpd/status/icloudpd-a')
        assert resp.get_json()['status'] == 'syncing'

    @patch('app._docker_api', side_effect=OSError("socket gone"))
    def test_socket_error_is_unknown_http_200(self, mock_api, client):
        resp = client.get('/api/icloudpd/status/icloudpd-a')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'unknown'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd homepage-api && python -m pytest tests/test_app.py::TestIcloudpdStatusEndpoint -v`
Expected: FAIL — `404 != 200` / `AttributeError: <module 'app'> does not have the attribute '_docker_logs'`.

- [ ] **Step 3: Implement the log helper**

Add to `app.py` near `_docker_api` (reuse the same `_UnixConn` pattern; the logs endpoint returns a raw multiplexed stream, not JSON):

```python
def _docker_logs(name, tail=250):
    """
    Return recent combined stdout/stderr logs for a container as text.
    The Docker logs endpoint returns a multiplexed stream: each frame is an
    8-byte header (stream byte, 3 zero bytes, 4-byte big-endian length)
    followed by the payload. Strip the headers.
    """
    import http.client
    import socket as _socket
    import struct

    class _UnixConn(http.client.HTTPConnection):
        def connect(self):
            self.sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            self.sock.connect('/var/run/docker.sock')

    conn = _UnixConn('localhost')
    try:
        conn.request('GET', f'/containers/{name}/logs?stdout=1&stderr=1&timestamps=1&tail={tail}')
        resp = conn.getresponse()
        raw = resp.read()
    finally:
        conn.close()

    out = []
    i = 0
    while i + 8 <= len(raw):
        header = raw[i:i + 8]
        # If this doesn't look like a frame header (no-TTY containers always
        # send headers; guard anyway), treat the rest as plain text.
        if header[0] in (0, 1, 2) and header[1:4] == b'\x00\x00\x00':
            (length,) = struct.unpack('>I', header[4:8])
            out.append(raw[i + 8:i + 8 + length].decode('utf-8', 'replace'))
            i += 8 + length
        else:
            out.append(raw[i:].decode('utf-8', 'replace'))
            break
    return ''.join(out)
```

- [ ] **Step 4: Implement the classifier and route**

```python
_ICLOUDPD_CONTAINERS = ('icloudpd-a', 'icloudpd-b')

# Log substrings, checked case-insensitively. Tune against real output on the
# server; keep the lists here so tuning is a one-line change.
_ICLOUDPD_AUTH_MARKERS = (
    'invalid authentication token',
    'waiting for mfa',
    'two-step authentication',
    'two-factor authentication',
    'password is required',
    'failed to login',
)
_ICLOUDPD_DRIVE_MARKER = 'backup drive not mounted or wrong drive'
_ICLOUDPD_DONE_MARKERS = (
    'all photos have been downloaded',
    'iteration completed',
)
_ICLOUDPD_PROGRESS_MARKERS = (
    'downloading ',
    'downloaded ',
)


def _rel_time(iso_ts):
    """'2026-09-06T04:15:03Z' -> '3 hours ago' (coarse)."""
    try:
        ts = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
    delta = datetime.now(ts.tzinfo) - ts
    secs = int(delta.total_seconds())
    if secs < 0:
        return 'just now'
    for unit, size in (('day', 86400), ('hour', 3600), ('minute', 60)):
        if secs >= size:
            n = secs // size
            return f'{n} {unit}{"s" if n != 1 else ""} ago'
    return 'just now'


def _classify_icloudpd(state, health, logs):
    lines = [ln for ln in logs.splitlines() if ln.strip()]
    lower = [ln.lower() for ln in lines]

    running = bool(state.get('Running'))
    if not running:
        return {'status': 'down', 'statusLabel': 'Stopped', 'lastSync': None,
                'lastSyncRelative': None, 'message': 'Container is not running'}

    if _ICLOUDPD_DRIVE_MARKER in '\n'.join(lower) or health == 'unhealthy':
        return {'status': 'drive_missing', 'statusLabel': 'Drive not mounted',
                'lastSync': None, 'lastSyncRelative': None,
                'message': 'Backup drive is not mounted or is the wrong drive'}

    # Walk newest -> oldest; first meaningful marker wins.
    last_done_ts = None
    for ln, lo in zip(reversed(lines), reversed(lower)):
        if any(m in lo for m in _ICLOUDPD_AUTH_MARKERS):
            return {'status': 'auth_required', 'statusLabel': 'Re-auth needed',
                    'lastSync': last_done_ts,
                    'lastSyncRelative': _rel_time(last_done_ts) if last_done_ts else None,
                    'message': 'Apple sign-in expired — open the web UI to re-authenticate'}
        if any(m in lo for m in _ICLOUDPD_DONE_MARKERS):
            last_done_ts = ln.split(' ', 1)[0]
            return {'status': 'ok', 'statusLabel': 'OK', 'lastSync': last_done_ts,
                    'lastSyncRelative': _rel_time(last_done_ts),
                    'message': 'Last sync completed'}
        if any(m in lo for m in _ICLOUDPD_PROGRESS_MARKERS):
            return {'status': 'syncing', 'statusLabel': 'Syncing', 'lastSync': None,
                    'lastSyncRelative': None, 'message': 'Sync in progress'}

    return {'status': 'unknown', 'statusLabel': 'Unknown', 'lastSync': None,
            'lastSyncRelative': None, 'message': 'No recent activity in logs'}


@app.route('/api/icloudpd/status/<name>')
def icloudpd_status(name):
    if name not in _ICLOUDPD_CONTAINERS:
        return jsonify({'error': 'unknown container'}), 404
    try:
        info = _docker_api(f'/containers/{name}/json')
        state = info.get('State', {}) or {}
        health = (state.get('Health') or {}).get('Status')
        logs = _docker_logs(name)
        result = _classify_icloudpd(state, health, logs)
    except Exception as e:
        result = {'status': 'unknown', 'statusLabel': 'Unknown', 'lastSync': None,
                  'lastSyncRelative': None, 'message': f'Cannot read container state: {e}'}
    result['name'] = name
    return jsonify(result)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd homepage-api && python -m pytest tests/test_app.py::TestIcloudpdStatusEndpoint -v`
Expected: PASS (all 7).

- [ ] **Step 6: Run the full suite**

Run: `cd homepage-api && python -m pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add homepage-api/app.py homepage-api/tests/test_app.py
git commit -m "feat: add icloudpd backup status endpoint to homepage-api"
```

---

## Task 3: Homepage dashboard integration

**Files:**
- Modify: `docker-compose.dashboard.yml` (homepage `environment:` block)
- Modify: `config/homepage/services-template.yaml` (new top-level group)

**Interfaces:**
- Consumes: `ICLOUD_A_LABEL` / `ICLOUD_B_LABEL` from `.env` (Task 1); `/api/icloudpd/status/icloudpd-a|b` (Task 2); containers `icloudpd-a` / `icloudpd-b` (Task 1).

- [ ] **Step 1: Pass the label vars to the homepage container**

In `docker-compose.dashboard.yml`, in the `homepage` service `environment:` block, after the transport vars, add:

```yaml
      # iCloud photo backup labels
      HOMEPAGE_VAR_ICLOUD_A_LABEL: ${ICLOUD_A_LABEL:-Photos A}
      HOMEPAGE_VAR_ICLOUD_B_LABEL: ${ICLOUD_B_LABEL:-Photos B}
```

- [ ] **Step 2: Add the Backups group to `services-template.yaml`**

Add as a new top-level list item (same indentation level as `- Today:` and `- Services:`), placed after the transport sections and before `- Services:`:

```yaml
- Backups:
    - "{{HOMEPAGE_VAR_ICLOUD_A_LABEL}}":
        icon: mdi-cloud-download
        href: https://icloud-a.{{HOMEPAGE_VAR_DOMAIN}}
        description: iCloud photo backup
        container: icloudpd-a
        server: my-docker
        showStats: true
        widget:
          type: customapi
          url: http://homepage-api:5000/api/icloudpd/status/icloudpd-a
          refreshInterval: 60000
          mappings:
            - field: statusLabel
              label: Status
            - field: lastSyncRelative
              label: Last sync
            - field: message
              label: Detail
    - "{{HOMEPAGE_VAR_ICLOUD_B_LABEL}}":
        icon: mdi-cloud-download
        href: https://icloud-b.{{HOMEPAGE_VAR_DOMAIN}}
        description: iCloud photo backup
        container: icloudpd-b
        server: my-docker
        showStats: true
        widget:
          type: customapi
          url: http://homepage-api:5000/api/icloudpd/status/icloudpd-b
          refreshInterval: 60000
          mappings:
            - field: statusLabel
              label: Status
            - field: lastSyncRelative
              label: Last sync
            - field: message
              label: Detail
```

- [ ] **Step 3: Lint the YAML**

Run: `python -c "import yaml,sys; yaml.safe_load(open('config/homepage/services-template.yaml'))"`
Note: the `{{HOMEPAGE_VAR_*}}` placeholders are valid YAML as written (quoted where used as keys). Expected: no exception.

- [ ] **Step 4: Validate compose**

Run: `make validate`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.dashboard.yml config/homepage/services-template.yaml
git commit -m "feat: show icloudpd backups on homepage dashboard"
```

---

## Task 4: Documentation

**Files:**
- Create: `docs/icloud-photos-backup.md`
- Modify: `SERVICES.md` (new subsections under a new "### Backup Services" heading after "### Location Services", plus two quick-reference rows; remove from "## Planned" if listed)
- Modify: `README.md` (one line where services are listed)

**Interfaces:** none (docs only).

- [ ] **Step 1: Write `docs/icloud-photos-backup.md`**

````markdown
# iCloud Photos Backup

Two `icloudpd` containers (`icloudpd-a`, `icloudpd-b`) continuously download two
iCloud photo libraries to an external drive. Defined in `docker-compose.photos.yml`.

## What this protects against

`icloudpd` runs **download-only**. It never modifies or deletes local files, and
the `--auto-delete` / `--delete-after-download` flags are deliberately not used.

- **Protects against:** accidental deletion of photos in iCloud, Apple account
  lockout or loss, cloud-side library corruption. The local copy always remains.
- **Does NOT protect against:** loss of the backup drive itself (single copy —
  drive failure, theft, corruption, ransomware, or an accidental delete on the
  drive loses the backup), and point-in-time gaps (a photo deleted in iCloud
  before it was ever downloaded is never captured). This is not a 3-2-1 backup.
  A second rotated drive is the practical way to add durability later.

## One-time setup

### 1. Mount the external drive

Find the drive UUID:

```bash
lsblk -f
```

Add to `/etc/fstab` (mount by UUID, `nofail` so a missing drive doesn't block
boot):

```
UUID=<drive-uuid>  /mnt/photos-backup  ext4  defaults,nofail  0  2
```

```bash
sudo mkdir -p /mnt/photos-backup
sudo mount -a
```

### 2. Create the drive sentinel

The containers refuse to run unless a sentinel file on the drive matches
`ICLOUD_BACKUP_DRIVE_ID`. Pick any unique string:

```bash
echo "photos-backup-2026-hitachi" | sudo tee /mnt/photos-backup/.backup-drive
sudo mkdir -p /mnt/photos-backup/account-a /mnt/photos-backup/account-b
```

### 3. Configure `.env`

Set at least: `ICLOUD_BACKUP_ROOT`, `ICLOUD_BACKUP_DRIVE_ID` (must equal the
sentinel contents), `ICLOUD_A_USERNAME` / `ICLOUD_B_USERNAME`,
`ICLOUD_A_SUBDIR` / `ICLOUD_B_SUBDIR`, `ICLOUD_A_LABEL` / `ICLOUD_B_LABEL`, and
the `ICLOUD_SMTP_*` + `ICLOUD_NOTIFICATION_EMAIL` values. See `.env.example`.

The Apple ID **password is not set in `.env`** — it is entered in the web UI.

### 4. Start and authenticate

```bash
make start
```

Then, for each account:

1. Open `https://icloud-a.${DOMAIN}` (and `https://icloud-b.${DOMAIN}`).
   Access is restricted to the home network / VPN by the `admin-secure`
   middleware.
2. Enter the Apple ID password, then the 2FA code sent to a trusted device.
3. The container begins downloading. First run can take hours to days depending
   on library size.

## Re-authentication (about every 2 months)

Apple expires the session roughly every two months. When that happens:

- `icloudpd` sends an email to `ICLOUD_NOTIFICATION_EMAIL`.
- The Homepage **Backups** tile shows **Re-auth needed**.

To fix: open the relevant `https://icloud-a.${DOMAIN}` / `icloud-b` URL and
enter a fresh 2FA code. No restart needed.

## Dashboard status meaning

| Tile status | Meaning |
|-------------|---------|
| OK | Last sync cycle completed; `Last sync` shows when |
| Syncing | A download pass is in progress |
| Re-auth needed | Apple sign-in expired — open the web UI |
| Drive not mounted | Sentinel check failed — drive missing or wrong drive |
| Stopped | Container not running |
| Unknown | No recent log activity / cannot read state |

## Replacing the drive

1. Copy existing data to the new drive (`rsync -a /mnt/photos-backup/ /mnt/new/`).
2. Write the sentinel: `echo "<new-id>" > /mnt/new/.backup-drive`.
3. Update `/etc/fstab` with the new UUID and `ICLOUD_BACKUP_DRIVE_ID` in `.env`.
4. `sudo mount -a && make restart`.

## Logs

```bash
make logs-icloudpd
```
````

- [ ] **Step 2: Update `SERVICES.md`**

Add after the "### Location Services" section (before "## Quick Reference"):

```markdown
### Backup Services

#### icloudpd (iCloud Photos)

Two containers (`icloudpd-a`, `icloudpd-b`) using `icloudpd/icloudpd:1.32.3`
download two iCloud photo libraries to an external drive on a continuous watch
loop. Each exposes a web UI at `https://icloud-a.${DOMAIN}` /
`https://icloud-b.${DOMAIN}` (home/VPN only) for password and 2FA entry.
Download-only — deletions in iCloud never propagate. Re-auth is needed roughly
every 2 months; `icloudpd` emails a notification and the Homepage Backups tile
shows the state. Full setup: `docs/icloud-photos-backup.md`.
```

Add to the Quick Reference table:

```markdown
| icloudpd A | https://icloud-a.${DOMAIN} | N/A |
| icloudpd B | https://icloud-b.${DOMAIN} | N/A |
```

If iCloud photo backup appears under "## Planned", remove it there.

- [ ] **Step 3: Update `README.md`**

Find where services are enumerated and add a bullet consistent with the existing style, e.g.:

```markdown
- **iCloud Photos backup** — `icloudpd` containers mirroring iCloud photo libraries to an external drive
```

- [ ] **Step 4: Commit**

```bash
git add docs/icloud-photos-backup.md SERVICES.md README.md
git commit -m "docs: document icloud photos backup setup and operation"
```

---

## Final verification (after all tasks)

- [ ] `make validate` passes.
- [ ] `cd homepage-api && python -m pytest -q` passes.
- [ ] `git log --oneline` shows 4 clean commits (plus the 2 spec commits).
- [ ] Grep check — no identifying data committed: `git grep -iE 'realname|actual-apple-id|/mnt/<real-path>'` returns nothing (manual sanity read of the diff).
- [ ] On the server (manual, post-merge): drive mounted, sentinel created, `make start`, both web UIs reachable and accept auth, Homepage Backups tile reaches **OK** after first sync, `make logs-icloudpd` shows watch-loop activity.

## Deferred / verify-on-server

- Exact `icloudpd` flag names for `1.32.3` (`--smtp-host`/`--smtp-port` names, `--no-progress-bar`, web UI provider flags) — confirm against `docker run --rm icloudpd/icloudpd:1.32.3 icloudpd --help` during Task 1; correct the compose file if they differ.
- Exact log strings for the classifier markers in Task 2 — tune `_ICLOUDPD_*_MARKERS` against real container output; the test strings are representative, not verbatim.
- Whether `1.32.3`'s web UI binds a path prefix or needs `--mfa-provider webui` *and* `--password-provider webui` both (plan assumes both) — verify at first auth.
