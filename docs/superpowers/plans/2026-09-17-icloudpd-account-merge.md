# iCloudpd Account Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two `icloudpd` containers (one per Apple account) into a single container that processes both accounts sequentially, simplifying the compose file, Traefik routing, and dashboard down to one of each, while correctly surfacing the worse of the two accounts' status on the single remaining dashboard tile.

**Architecture:** `docker-compose.photos.yml` goes from two services sharing a YAML anchor to one `icloudpd` service running icloudpd with two `--username`/`--directory` pairs (icloudpd's own native multi-account support). The drive guard and healthcheck are unchanged, just wrapping one process instead of two. `homepage-api`'s classifier gains a log-segmentation pass (split on `Processing user: <email>` markers) so "worst status wins" is computed correctly instead of naively scanning the whole shared log.

**Tech Stack:** Docker Compose, `icloudpd/icloudpd:1.32.3`, Flask (homepage-api, Python), pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-icloudpd-account-merge-design.md` (and the original `docs/superpowers/specs/2026-09-06-icloud-photos-backup-design.md` for constraints that still apply)

## Global Constraints

- **This is a fresh-start migration, confirmed with the user.** Both accounts re-authenticate from scratch. Existing downloaded files under `/mnt/photos-backup/account-a` and `/mnt/photos-backup/account-b` are NOT touched by anything in this plan — icloudpd's own dedup-by-existing-file behavior means re-auth does not re-download them.
- **No identifying data in committed code.** Same rule as the original feature — all account/drive values stay in `.env`.
- **Never add `--auto-delete` or `--delete-after-download`** to the icloudpd command.
- **Pinned image stays `icloudpd/icloudpd:1.32.3`.**
- **New container/service/hostname: `icloudpd`** (single, generic — not `icloudpd-a`). Traefik host `icloud.${DOMAIN}`, replacing both `icloud-a` and `icloud-b`.
- **Dashboard shows ONE combined status, reflecting the worst of the two accounts** by severity `auth_required` > `syncing` > `unknown` > `ok`. Per-account visibility is intentionally not preserved (user's explicit choice).
- **Cookie directory consolidates to one shared path**: `./data/icloudpd/cookies` (icloudpd stores session files per-username internally, so sharing one directory across accounts is safe per icloudpd's own docs).
- **Staggering (`ICLOUD_B_INTERVAL`, `ICLOUD_B_START_DELAY`) is removed**, not preserved — one sequential process never contends with itself, so the workaround no longer applies.
- **homepage-api internal URL** for the Homepage widget is `http://homepage-api:5000` (container's internal gunicorn port).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `docker-compose.photos.yml` (modify) | Collapse to one `icloudpd` service; single command covering both accounts. |
| `.env.example` (modify) | Drop `ICLOUD_B_INTERVAL`/`ICLOUD_B_START_DELAY`/`ICLOUD_A_LABEL`/`ICLOUD_B_LABEL`; rename `ICLOUD_A_INTERVAL`→`ICLOUD_INTERVAL`; add `ICLOUD_LABEL`. |
| `Makefile` (modify) | `logs-icloudpd` target now follows one container. |
| `homepage-api/app.py` (modify) | Route drops its `<name>` parameter; classifier gains per-account log segmentation + worst-of combination. |
| `homepage-api/tests/test_app.py` (modify) | Replace `TestIcloudpdStatusEndpoint` with tests for the new route shape and segmentation/worst-of logic. |
| `docker-compose.dashboard.yml` (modify) | One `HOMEPAGE_VAR_ICLOUD_LABEL` var instead of two. |
| `config/homepage/services-template.yaml` (modify) | Backups group drops to one entry. |
| `docs/icloud-photos-backup.md` (modify) | Rewritten for the single-container flow. |
| `SERVICES.md` (modify) | One icloudpd entry/row instead of two. |

`config/homepage/settings-template.yaml` needs **no change** — the `Backups: {style: row, columns: 2}` layout entry applies to the group regardless of how many services are inside it.

---

## Task 1: Compose file, environment, Makefile

**Files:**
- Modify: `docker-compose.photos.yml` (full rewrite of the `services:` block)
- Modify: `.env.example:222-260` (the iCloud Photos Backup block)
- Modify: `Makefile:342` (`logs-icloudpd` target)
- Create (empty, git-tracked): `data/icloudpd/cookies/.gitkeep`

**Interfaces:**
- Produces: one container named `icloudpd`; Traefik router `icloud` at `icloud.${DOMAIN}` → port 8080; env vars `ICLOUD_INTERVAL`, `ICLOUD_LABEL` consumed by Task 3.

- [ ] **Step 1: Rewrite `docker-compose.photos.yml`**

Replace the entire file with:

```yaml
# iCloud Photos backup — one icloudpd container handling two Apple accounts
# sequentially (icloudpd's own native multi-account support via repeated
# --username/--directory pairs). See docs/icloud-photos-backup.md for setup.
# All identifying values are in .env.
#
# The Apple ID passwords are entered via the container's web UI (never
# stored in .env or the repo) and persisted only in ./data/icloudpd/cookies.

services:
  icloudpd:
    image: icloudpd/icloudpd:1.32.3
    container_name: icloudpd
    restart: unless-stopped
    # The image's own ENTRYPOINT is a dispatcher script that requires argv[0] to
    # literally be "icloud" or "icloudpd" (see /app/entrypoint.sh in the image) —
    # it errors on any other command, including a shell wrapper. Override the
    # entrypoint itself so our drive-guard script runs instead of that dispatcher.
    # The icloudpd binary lives at /app/icloudpd and is NOT on PATH, so the
    # command script below must call it by full path.
    entrypoint: ["/bin/sh", "-c"]
    networks:
      - homeserver
    environment:
      TZ: ${TIMEZONE:-UTC}
      ICLOUD_BACKUP_DRIVE_ID: ${ICLOUD_BACKUP_DRIVE_ID}
    volumes:
      - ${ICLOUD_BACKUP_ROOT}:/drive
      - ./data/icloudpd/cookies:/cookies
    command:
      - |
        if [ "$$(cat /drive/.backup-drive 2>/dev/null)" != "$$ICLOUD_BACKUP_DRIVE_ID" ]; then
          echo "backup drive not mounted or wrong drive"; sleep 3600; exit 1
        fi
        # Re-check every 5 min: if the drive drops out mid-run, stop writing (kill PID 1,
        # restart policy lands us back at the guard above).
        while sleep 300; do
          [ "$$(cat /drive/.backup-drive 2>/dev/null)" = "$$ICLOUD_BACKUP_DRIVE_ID" ] || {
            echo "backup drive disappeared mid-run"; kill 1
          }
        done &
        exec /app/icloudpd \
          --cookie-directory /cookies \
          --watch-with-interval "${ICLOUD_INTERVAL:-21600}" \
          --folder-structure "${ICLOUD_FOLDER_STRUCTURE}" \
          --password-provider webui \
          --mfa-provider webui \
          --smtp-host "${ICLOUD_SMTP_HOST}" \
          --smtp-port "${ICLOUD_SMTP_PORT:-587}" \
          --smtp-username "${ICLOUD_SMTP_USERNAME}" \
          --smtp-password "${ICLOUD_SMTP_PASSWORD}" \
          --notification-email "${ICLOUD_NOTIFICATION_EMAIL}" \
          --no-progress-bar \
          --username "${ICLOUD_A_USERNAME}" --directory "/drive/${ICLOUD_A_SUBDIR}" \
          --username "${ICLOUD_B_USERNAME}" --directory "/drive/${ICLOUD_B_SUBDIR}"
    healthcheck:
      test: ["CMD-SHELL", "test \"$$(cat /drive/.backup-drive 2>/dev/null)\" = \"$$ICLOUD_BACKUP_DRIVE_ID\""]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.icloud.rule=Host(`icloud.${DOMAIN}`)"
      - "traefik.http.routers.icloud.entrypoints=websecure"
      - "traefik.http.routers.icloud.tls=true"
      - "traefik.http.services.icloud.loadbalancer.server.port=8080"
      - "traefik.http.routers.icloud.middlewares=admin-secure"

networks:
  homeserver:
    external: true
    name: home-server-stack_homeserver
```

Notes for the implementer:
- The `x-icloudpd-common` YAML anchor is gone — with one service there's nothing left to share via an anchor.
- `--username`/`--directory` pairs: everything on the `exec /app/icloudpd \` line before the first `--username` is a shared default (icloudpd's own convention — options before the first `--username` apply to every account that follows); `--username "${ICLOUD_A_USERNAME}" --directory "/drive/${ICLOUD_A_SUBDIR}"` and the `B` equivalent are each scoped to their own account only.
- `$$` vs `$` follows the exact same rule as before: `$$` for anything the container's own shell must expand at runtime (the drive-guard comparison), single `$` for anything Docker Compose expands from `.env` at render time.

- [ ] **Step 2: Verify the compose file renders**

Run: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml config --quiet`

Expected: exits 0. Requires the updated `.env` vars from Step 3 — set throwaway values locally if needed for the check (this stack only runs `docker` on the server; if Docker is unavailable in your environment, note that and treat this as a server-verify item, matching how the original feature's Task 1 handled the same limitation).

- [ ] **Step 3: Update `.env.example`**

Replace the iCloud Photos Backup block (currently `.env.example:222-260`) with:

```bash
# =============================================================================
# iCloud Photos Backup (icloudpd)
# =============================================================================
# One container backs up two iCloud photo libraries to an external drive,
# processing them sequentially. The Apple ID PASSWORDS are NOT set here —
# they are entered once, per account, in the web UI at
# https://icloud.${DOMAIN}. See docs/icloud-photos-backup.md for full setup.

# Absolute host path where the external backup drive is mounted (see fstab setup).
ICLOUD_BACKUP_ROOT=/mnt/photos-backup
# Identity string; must equal the contents of ${ICLOUD_BACKUP_ROOT}/.backup-drive.
# Container refuses to run unless it matches (guards against unmounted/wrong drive).
ICLOUD_BACKUP_DRIVE_ID=change-me-unique-drive-id

# Continuous sync cadence in seconds, covering both accounts each cycle
# (icloudpd processes them sequentially within one watch loop).
ICLOUD_INTERVAL=21600

# icloudpd folder layout within each account's tree.
ICLOUD_FOLDER_STRUCTURE={:%Y/%m}

# SMTP for icloudpd's "2FA expired, re-auth needed" notification email.
ICLOUD_SMTP_HOST=smtp.example.com
ICLOUD_SMTP_PORT=587
ICLOUD_SMTP_USERNAME=alerts@example.com
ICLOUD_SMTP_PASSWORD=app_password_here
ICLOUD_NOTIFICATION_EMAIL=you@example.com

# Dashboard tile display name (covers both accounts — the tile shows one
# combined status, the worse of the two).
ICLOUD_LABEL="Photo Backups"

# Account A
ICLOUD_A_USERNAME=appleid-a@example.com
ICLOUD_A_SUBDIR=account-a

# Account B
ICLOUD_B_USERNAME=appleid-b@example.com
ICLOUD_B_SUBDIR=account-b
```

Note: `ICLOUD_LABEL` is quoted (unlike the old unquoted `ICLOUD_A_LABEL=Photos A` this replaces) — several of this repo's scripts `source .env` directly, and an unquoted value containing a space breaks that (`VAR=word1 word2` runs `word2` as a command). This was a real bug found and fixed during the original feature's server deployment.

- [ ] **Step 4: Create the shared cookie directory placeholder**

```bash
mkdir -p data/icloudpd/cookies
touch data/icloudpd/cookies/.gitkeep
```

- [ ] **Step 5: Update the Makefile**

Change the `logs-icloudpd` target (`Makefile:341-342`) from:

```make
logs-icloudpd:
	@$(COMPOSE) logs -f icloudpd-a icloudpd-b
```

to:

```make
logs-icloudpd:
	@$(COMPOSE) logs -f icloudpd
```

The `COMPOSE` variable itself (`Makefile:28`) and the header comment already reference `docker-compose.photos.yml` by filename, not service name — no change needed there.

- [ ] **Step 6: Validate**

Run: `make validate`
Expected: PASS if Docker is available; otherwise note it as a server-verify item (same as Step 2).

- [ ] **Step 7: Commit**

```bash
git add docker-compose.photos.yml .env.example Makefile data/icloudpd/cookies/.gitkeep
git commit -m "feat: merge icloudpd-a/icloudpd-b into one multi-account container"
```

---

## Task 2: homepage-api classifier — per-account segmentation, worst-of

**Files:**
- Modify: `homepage-api/app.py` (route + classifier)
- Modify: `homepage-api/tests/test_app.py` (replace `TestIcloudpdStatusEndpoint`)

**Interfaces:**
- Consumes: `_docker_api`, `_docker_logs`, `_rel_time`, `_demux_docker_stream` (all unchanged, defined earlier in `app.py`).
- Produces: `GET /api/icloudpd/status` (no path parameter) returning the same response shape as before: `{"name", "status", "statusLabel", "lastSync", "lastSyncRelative", "message"}`. Consumed by Task 3's dashboard widget.

- [ ] **Step 1: Write the failing tests**

Replace the entire `TestIcloudpdStatusEndpoint` class in `homepage-api/tests/test_app.py` with:

```python
class TestIcloudpdStatusEndpoint:
    """Tests for /api/icloudpd/status (single merged container)"""

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_both_accounts_ok_is_ok(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:10Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['statusLabel'] == 'OK'
        assert data['name'] == 'icloudpd'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_one_account_auth_required_is_worst(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:08Z ERROR Invalid authentication token, please log in\n"
            "2026-09-17T04:00:09Z INFO Waiting for MFA code via webui\n"
        )
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'auth_required'
        assert data['statusLabel'] == 'Re-auth needed'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_one_account_syncing_beats_ok(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:08Z INFO Downloading 12 original photos to /drive/account-b\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'syncing'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_drive_missing_short_circuits_regardless_of_account_lines(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'unhealthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'drive_missing'
        assert data['statusLabel'] == 'Drive not mounted'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_not_running_is_down(self, mock_api, mock_logs, client):
        mock_api.return_value = {'State': {'Status': 'exited', 'Running': False, 'Health': None}}
        mock_logs.return_value = ""
        resp = client.get('/api/icloudpd/status')
        data = resp.get_json()
        assert data['status'] == 'down'
        assert data['statusLabel'] == 'Stopped'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_stale_drive_marker_before_recovery_is_not_drive_missing(self, mock_api, mock_logs, client):
        """A drive-guard failure from a previous container lifetime, followed by
        real account activity proving the guard has since passed, must not pin
        the status to drive_missing."""
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = (
            "2026-09-17T01:00:00Z backup drive not mounted or wrong drive\n"
            "2026-09-17T04:00:00Z INFO Processing user: alice@example.com\n"
            "2026-09-17T04:00:05Z INFO All photos have been downloaded\n"
            "2026-09-17T04:00:06Z INFO Processing user: bob@example.com\n"
            "2026-09-17T04:00:10Z INFO All photos have been downloaded\n"
        )
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'ok'

    @patch('app._docker_logs')
    @patch('app._docker_api')
    def test_no_account_activity_yet_is_unknown(self, mock_api, mock_logs, client):
        mock_api.return_value = {
            'State': {'Status': 'running', 'Running': True,
                      'StartedAt': '2026-09-17T00:00:00Z', 'Health': {'Status': 'healthy'}}
        }
        mock_logs.return_value = "2026-09-17T04:00:00Z INFO Starting web server for WebUI authentication...\n"
        resp = client.get('/api/icloudpd/status')
        assert resp.get_json()['status'] == 'unknown'

    @patch('app._docker_api', side_effect=OSError("socket gone"))
    def test_socket_error_is_unknown_http_200(self, mock_api, client):
        resp = client.get('/api/icloudpd/status')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'unknown'
```

(The `TestIcloudpdStatusEndpoint` tests for `_rel_time` and `_demux_docker_stream` — `test_rel_time_parses_nanosecond_docker_timestamp` and `test_demux_docker_stream_parses_multiplexed_frames` — are unaffected by this change and can stay as-is; leave them in place if they're separate methods on the class, since neither `_rel_time` nor `_demux_docker_stream` changes in this task.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd homepage-api && python -m pytest tests/test_app.py::TestIcloudpdStatusEndpoint -v`
Expected: FAIL — the route is still `/api/icloudpd/status/<name>` and returns 404 for a bare `/api/icloudpd/status` request; `_ICLOUDPD_CONTAINERS` allowlist logic doesn't match the new tests' expectations.

- [ ] **Step 3: Replace the classifier and route in `homepage-api/app.py`**

Replace the block from `_ICLOUDPD_CONTAINERS = ('icloudpd-a', 'icloudpd-b')` through the end of `icloudpd_status` (currently lines ~627 to the end of the route function) with:

```python
_ICLOUDPD_CONTAINER = 'icloudpd'

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
_ICLOUDPD_USER_MARKER = 'processing user:'

# Worst status wins when combining multiple accounts' results.
_ICLOUDPD_SEVERITY = {'auth_required': 3, 'syncing': 2, 'unknown': 1, 'ok': 0}


def _rel_time(iso_ts):
    """'2026-09-06T04:15:03Z' -> '3 hours ago' (coarse)."""
    try:
        s = iso_ts.replace('Z', '+00:00')
        # Docker emits nanosecond precision; datetime accepts at most microseconds
        s = re.sub(r'(\.\d{6})\d+', r'\1', s)
        ts = datetime.fromisoformat(s)
    except (ValueError, AttributeError, TypeError):
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


def _classify_account_segment(seg_lines, seg_lower):
    """Classify one account's slice of the log, newest line wins (same logic
    as the original single-account classifier)."""
    last_done_ts = None
    for ln, lo in zip(reversed(seg_lines), reversed(seg_lower)):
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


def _classify_icloudpd(state, health, logs):
    lines = [ln for ln in logs.splitlines() if ln.strip()]
    lower = [ln.lower() for ln in lines]

    running = bool(state.get('Running'))
    if not running:
        return {'status': 'down', 'statusLabel': 'Stopped', 'lastSync': None,
                'lastSyncRelative': None, 'message': 'Container is not running'}

    _drive_result = {'status': 'drive_missing', 'statusLabel': 'Drive not mounted',
                     'lastSync': None, 'lastSyncRelative': None,
                     'message': 'Backup drive is not mounted or is the wrong drive'}
    if health == 'unhealthy':
        return _drive_result

    # The drive guard runs before icloudpd starts, so its failure line always
    # precedes any "Processing user:" activity from a lifetime where the guard
    # passed. Scan newest-first but stop at the first "Processing user:" line —
    # a drive-marker line older than that is from a since-recovered earlier
    # lifetime and must not pin the status.
    for lo in reversed(lower):
        if _ICLOUDPD_USER_MARKER in lo:
            break
        if _ICLOUDPD_DRIVE_MARKER in lo:
            return _drive_result

    # Split into per-account segments: each starts at a "Processing user: X"
    # line and runs to just before the next such line (or end of tail).
    segments_by_user = {}
    current_user = None
    current_lines = []
    current_lower = []
    for ln, lo in zip(lines, lower):
        idx = lo.find(_ICLOUDPD_USER_MARKER)
        if idx != -1:
            if current_user is not None:
                segments_by_user[current_user] = (current_lines, current_lower)
            current_user = ln[idx + len(_ICLOUDPD_USER_MARKER):].strip()
            current_lines = []
            current_lower = []
        else:
            current_lines.append(ln)
            current_lower.append(lo)
    if current_user is not None:
        segments_by_user[current_user] = (current_lines, current_lower)

    if not segments_by_user:
        return {'status': 'unknown', 'statusLabel': 'Unknown', 'lastSync': None,
                'lastSyncRelative': None, 'message': 'No recent activity in logs'}

    results = [_classify_account_segment(seg_lines, seg_lower)
               for seg_lines, seg_lower in segments_by_user.values()]
    return max(results, key=lambda r: _ICLOUDPD_SEVERITY.get(r['status'], -1))


@app.route('/api/icloudpd/status')
def icloudpd_status():
    name = _ICLOUDPD_CONTAINER
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

This removes the old `_ICLOUDPD_CONTAINERS` allowlist and the 404-for-unknown-name path (there is no longer a `<name>` URL parameter to validate).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd homepage-api && python -m pytest tests/test_app.py::TestIcloudpdStatusEndpoint -v`
Expected: PASS (all 8 new tests).

- [ ] **Step 5: Run the full suite**

Run: `cd homepage-api && python -m pytest -q`
Expected: PASS, no regressions. (The `_rel_time` and `_demux_docker_stream` tests should already be passing unchanged, since neither function's code changed.)

- [ ] **Step 6: Commit**

```bash
git add homepage-api/app.py homepage-api/tests/test_app.py
git commit -m "feat: classify icloudpd status per-account, worst-of, single route"
```

---

## Task 3: Homepage dashboard

**Files:**
- Modify: `docker-compose.dashboard.yml:75-76`
- Modify: `config/homepage/services-template.yaml:185-221` (the Backups group)

**Interfaces:**
- Consumes: `ICLOUD_LABEL` from `.env` (Task 1); `GET /api/icloudpd/status` (Task 2); container `icloudpd` (Task 1).

- [ ] **Step 1: Update the label env var passthrough**

In `docker-compose.dashboard.yml`, replace:

```yaml
      HOMEPAGE_VAR_ICLOUD_A_LABEL: ${ICLOUD_A_LABEL:-Photos A}
      HOMEPAGE_VAR_ICLOUD_B_LABEL: ${ICLOUD_B_LABEL:-Photos B}
```

with:

```yaml
      HOMEPAGE_VAR_ICLOUD_LABEL: ${ICLOUD_LABEL:-Photo Backups}
```

- [ ] **Step 2: Collapse the Backups group to one entry**

In `config/homepage/services-template.yaml`, replace the entire Backups group (currently lines 185-221) with:

```yaml
- Backups:
    - "{{HOMEPAGE_VAR_ICLOUD_LABEL}}":
        icon: mdi-cloud-download
        href: https://icloud.{{HOMEPAGE_VAR_DOMAIN}}
        description: iCloud photo backup
        container: icloudpd
        server: my-docker
        showStats: true
        widget:
          type: customapi
          url: http://homepage-api:5000/api/icloudpd/status
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
Expected: no exception. If `yaml` isn't importable in your environment, this is a server-verify item (same limitation the original feature's Task 3 hit).

- [ ] **Step 4: Validate compose**

Run: `make validate`
Expected: PASS (or server-verify, per Task 1 Step 2's note).

- [ ] **Step 5: Commit**

```bash
git add docker-compose.dashboard.yml config/homepage/services-template.yaml
git commit -m "feat: single combined dashboard tile for merged icloudpd container"
```

---

## Task 4: Documentation

**Files:**
- Modify: `docs/icloud-photos-backup.md` (full rewrite)
- Modify: `SERVICES.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Rewrite `docs/icloud-photos-backup.md`**

Replace the file's content with:

````markdown
# iCloud Photos Backup

One `icloudpd` container backs up two iCloud photo libraries to an external
drive, processing both accounts sequentially each cycle (icloudpd's own
native multi-account support). Defined in `docker-compose.photos.yml`.

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
- **Partial mid-run protection:** a start-up guard plus a 5-minute re-check stop
  new writes if the backup drive drops out, but a write in the few-minute gap
  before detection could land on the server's system disk. Keep an eye on the
  dashboard tile.

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

The container refuses to run unless a sentinel file on the drive matches
`ICLOUD_BACKUP_DRIVE_ID`. Pick any unique string:

```bash
echo "photos-backup-drive-01" | sudo tee /mnt/photos-backup/.backup-drive
sudo mkdir -p /mnt/photos-backup/account-a /mnt/photos-backup/account-b
```

(the `account-a` / `account-b` directory names must match `ICLOUD_A_SUBDIR` /
`ICLOUD_B_SUBDIR` in `.env`.)

### 3. Configure `.env`

Set at least: `ICLOUD_BACKUP_ROOT`, `ICLOUD_BACKUP_DRIVE_ID` (must equal the
sentinel contents), `ICLOUD_A_USERNAME` / `ICLOUD_B_USERNAME`,
`ICLOUD_A_SUBDIR` / `ICLOUD_B_SUBDIR`, `ICLOUD_LABEL`, and the `ICLOUD_SMTP_*`
+ `ICLOUD_NOTIFICATION_EMAIL` values. See `.env.example`.

The Apple ID **passwords are not set in `.env`** — each is entered in the web
UI, one account at a time (see Step 4).

Any `$` characters in `.env` values (for example an SMTP password) must be
escaped as `$$` for Docker Compose — a stack-wide rule, see `.env.example`.

### 4. Start and authenticate

```bash
make start
```

Then open `https://icloud.${DOMAIN}` — access is restricted to the home
network / VPN by the `admin-secure` middleware. Because icloudpd processes
accounts sequentially, the web UI prompts for **account A first**; once that
password + 2FA code is entered, it moves on to **account B**. There is no
way to authenticate both at once — expect two separate password/2FA prompts,
one after the other, not simultaneously.

The container begins downloading once both are authenticated. First run can
take hours to days depending on library size.

## Re-authentication (about every 2 months)

Apple expires each account's session independently, roughly every two
months. When either needs it:

- `icloudpd` sends an email to `ICLOUD_NOTIFICATION_EMAIL`.
- The Homepage **Backups** tile shows **Re-auth needed** — this reflects the
  *worse* of the two accounts' states, so it doesn't say which account. If
  it's not obvious from context (e.g. you know account B just had its 2FA
  window expire), check `make logs-icloudpd` for the specific
  `Processing user: <email>` line the error appears under.

To fix: open `https://icloud.${DOMAIN}` and enter a fresh 2FA code for
whichever account needs it. No restart required.

## Dashboard status meaning

The tile shows one status covering both accounts — whichever is worse, by
this order (worst first): **Re-auth needed** > **Syncing** > **Unknown** >
**OK**. A drive problem or the container being stopped overrides both
accounts' states entirely.

| Tile status | Meaning |
|-------------|---------|
| OK | Both accounts' last sync cycle completed; `Last sync` shows the more recent of the two |
| Syncing | At least one account has a download pass in progress |
| Re-auth needed | At least one account's Apple sign-in expired — open the web UI |
| Drive not mounted | Sentinel check failed — drive missing or wrong drive |
| Stopped | Container not running |
| Unknown | No recent log activity for at least one account / cannot read state |

## Replacing the drive

1. Copy existing data to the new drive (`rsync -a /mnt/photos-backup/ /mnt/new/`).
2. Write the sentinel: `echo "<new-id>" > /mnt/new/.backup-drive`.
3. Update `/etc/fstab` with the new UUID and `ICLOUD_BACKUP_DRIVE_ID` in `.env`.
4. `sudo mount -a && make restart`.

## Logs

```bash
make logs-icloudpd
```

Each account's activity is marked by its own `Processing user: <email>` line
— search for the relevant address to see just that account's recent history.
````

- [ ] **Step 2: Update `SERVICES.md`**

Replace the `#### icloudpd (iCloud Photos)` section (currently around
`SERVICES.md:112-120`) with:

```markdown
#### icloudpd (iCloud Photos)

One container using `icloudpd/icloudpd:1.32.3` downloads two iCloud photo
libraries to an external drive on a continuous watch loop, processing both
accounts sequentially. Exposes a web UI at `https://icloud.${DOMAIN}`
(home/VPN only) for password and 2FA entry — one account is prompted at a
time. Download-only — deletions in iCloud never propagate. Re-auth is
needed roughly every 2 months per account; `icloudpd` emails a notification
and the Homepage Backups tile shows the worse of the two accounts' status.
Full setup: `docs/icloud-photos-backup.md`.
```

Replace the two Quick Reference rows (`SERVICES.md:137-138`):

```markdown
| icloudpd A | https://icloud-a.${DOMAIN} | N/A |
| icloudpd B | https://icloud-b.${DOMAIN} | N/A |
```

with one:

```markdown
| icloudpd | https://icloud.${DOMAIN} | N/A |
```

- [ ] **Step 3: Commit**

```bash
git add docs/icloud-photos-backup.md SERVICES.md
git commit -m "docs: update icloud photos backup docs for merged single container"
```

---

## Final verification (after all tasks)

- [ ] `make validate` passes.
- [ ] `cd homepage-api && python -m pytest -q` passes.
- [ ] `git log --oneline` shows 4 clean commits (plus the design-spec commit).
- [ ] Grep check for identifying data in the diff: manual read confirms no real emails/paths were introduced.

## Server migration (manual, after merge — cannot be scripted, and this is the only way to verify it)

1. Deploy the merged branch to the server (`git fetch && git checkout <branch> && git pull`).
2. Remove the two old containers: `docker compose ... rm -sf icloudpd-a icloudpd-b` (or let `docker compose up -d` reconcile — the old service names no longer exist in the compose file, so they become orphans; `docker rm -f icloudpd-a icloudpd-b` is the explicit path).
3. Delete the old cookie directories: `rm -rf data/icloudpd/a data/icloudpd/b` (the new shared `data/icloudpd/cookies/` is created fresh by Task 1's `.gitkeep`).
4. Update the server's `.env`: remove `ICLOUD_B_INTERVAL`/`ICLOUD_B_START_DELAY`/`ICLOUD_A_LABEL`/`ICLOUD_B_LABEL`, rename `ICLOUD_A_INTERVAL` → `ICLOUD_INTERVAL`, add `ICLOUD_LABEL` (quoted if it contains a space).
5. `make validate && make update` (or `up -d icloudpd` scoped to just this service).
6. Confirm `/mnt/photos-backup/account-a` and `account-b` are unchanged (`find ... -type f | wc -l` before and after should match) — no data should move or disappear from this migration.
7. Open `https://icloud.${DOMAIN}`, authenticate account A, then account B, confirming the sequential-prompt behavior described in the doc. If the UX is actually simultaneous or ambiguous about which account is being prompted, note it — this was flagged as unverified in the design spec.
8. Confirm `curl`/`docker exec homepage-api curl -s http://localhost:5000/api/icloudpd/status` (no container name in the URL now) returns a sensible combined status, and the Homepage Backups tile shows one entry.
9. Retire the two old Traefik hosts from memory/bookmarks — `icloud-a.${DOMAIN}` and `icloud-b.${DOMAIN}` no longer resolve to anything.
