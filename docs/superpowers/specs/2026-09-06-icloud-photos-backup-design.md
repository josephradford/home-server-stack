# iCloud Photos Backup — Design

**Date:** 2026-09-06
**Status:** Approved for planning

## Problem

Back up two separate iCloud photo libraries to an external hard drive on the
home server. The stack's committed code must contain no information identifying
the account holders or the drive — all of that is private configuration. The
two containers must appear on the Homepage dashboard, and the dashboard must
show whether each backup is healthy. Apple expires 2FA roughly every two
months, so periodic re-authentication is expected and the operator must be
notified when it is needed.

## Non-goals

- No changes to Alertmanager / Prometheus alert wiring. icloudpd's own SMTP
  notification plus the Homepage status tile are the whole notification story.
- No shared/deduplicated storage between the two accounts. Each account gets a
  complete, standalone backup tree.
- No automated drive provisioning. The fstab setup is documented and performed
  once by the operator.

## Approach

Two `icloudpd/icloudpd` containers in a new `docker-compose.photos.yml`,
running continuous watch mode, each serving its own web UI for re-auth, each
writing to a private subdirectory of the external drive. A new `homepage-api`
endpoint classifies each container's health by inspecting Docker state and
recent logs; the Homepage dashboard renders that as a status tile.

### Naming and privacy

- Container names: `icloudpd-a`, `icloudpd-b` (generic, non-identifying).
- All identifying / sensitive values live only in `.env`. `.env.example` ships
  generic placeholders. Nothing in committed code names a person or the drive.

Environment variables (added to `.env.example` with placeholder values):

```
# --- iCloud Photos backup (icloudpd) ---

# External drive: absolute mount path on the host, and an identity string that
# must match the contents of the drive's sentinel file (see docs).
ICLOUD_BACKUP_ROOT=/mnt/photos-backup
ICLOUD_BACKUP_DRIVE_ID=change-me-drive-id

# Continuous sync cadence (seconds). Account B is offset by ICLOUD_B_INTERVAL
# and a start delay so the two heavy passes drift apart on a spinning disk.
ICLOUD_A_INTERVAL=21600
ICLOUD_B_INTERVAL=23400
ICLOUD_B_START_DELAY=1800

# Folder layout within each account's tree.
ICLOUD_FOLDER_STRUCTURE={:%Y/%m}

# SMTP for icloudpd's "2FA expired" notification email.
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

### Container definition

`docker-compose.photos.yml` uses a YAML anchor for the shared body. Per
container:

- `image: icloudpd/icloudpd:<pinned-version>` (pin to the current release; the
  README/SERVICES version table convention applies).
- `restart: unless-stopped`, `networks: [homeserver]`.
- `environment:` `TZ` (reuse existing stack `TZ`/timezone convention),
  `ICLOUD_BACKUP_DRIVE_ID`, and the account-specific values.
- Volumes:
  - `${ICLOUD_BACKUP_ROOT}:/drive`
  - `./data/icloudpd/a/cookies:/cookies` (and `b` for the second)
- `command:` a `sh -c` wrapper (see guard below) that ends with
  `exec icloudpd <flags>`.
- `healthcheck:` runs the same drive check the wrapper does.
- Traefik labels routing `icloud-a.${DOMAIN}` / `icloud-b.${DOMAIN}` →
  container port `8080`, `entrypoints=websecure`, `tls=true`, middleware
  `admin-secure` (RFC1918 + VPN allowlist, same as other admin UIs).

icloudpd flags:

```
icloudpd
  --directory /drive/${ICLOUD_x_SUBDIR}
  --username ${ICLOUD_x_USERNAME}
  --cookie-directory /cookies
  --watch-with-interval ${ICLOUD_x_INTERVAL}
  --folder-structure ${ICLOUD_FOLDER_STRUCTURE}
  --mfa-provider webui
  --smtp-host ${ICLOUD_SMTP_HOST}
  --smtp-port ${ICLOUD_SMTP_PORT}
  --smtp-username ${ICLOUD_SMTP_USERNAME}
  --smtp-password ${ICLOUD_SMTP_PASSWORD}
  --notification-email ${ICLOUD_NOTIFICATION_EMAIL}
  --no-progress-bar
```

Exact flag names to be confirmed against `icloudpd --help` for the pinned
version during implementation (web UI provider flag, SMTP flags, and progress
flag have varied across releases). If the pinned image's web UI listens on a
non-8080 port or needs an explicit enable flag, adjust the Traefik label and
command accordingly.

### External drive guard

The drive is mounted by UUID via `/etc/fstab` with `nofail`, at
`${ICLOUD_BACKUP_ROOT}`. The operator creates a sentinel file once:

```
echo "<drive-id>" > ${ICLOUD_BACKUP_ROOT}/.backup-drive
```

and sets `ICLOUD_BACKUP_DRIVE_ID=<drive-id>` in `.env`.

Guard logic, used identically in both the container `command` wrapper and the
`healthcheck`:

```sh
test "$(cat /drive/.backup-drive 2>/dev/null)" = "$ICLOUD_BACKUP_DRIVE_ID" \
  || { echo "backup drive not mounted or wrong drive"; exit 1; }
```

In the `command` wrapper, a failed check logs the message, `sleep 3600`, then
`exit 1` (so `restart: unless-stopped` retries hourly rather than hot-looping,
and the log line is available for the status endpoint to classify). This
prevents icloudpd from ever writing into an unmounted mount point (which would
be the OS SSD) or into an unexpected drive.

Drive replacement is a documented procedure: write the sentinel on the new
drive, update `ICLOUD_BACKUP_DRIVE_ID` and the fstab UUID, restart.

### Concurrency

Both containers may sync simultaneously without conflict: they write to
disjoint subtrees (`/drive/account-a` vs `/drive/account-b`), hold separate
cookie directories, and use separate Apple accounts/API sessions. icloudpd
takes no global lock and only touches paths under its `--directory`.

To reduce seek contention on a spinning disk, account B runs on a slightly
longer interval (`ICLOUD_B_INTERVAL`) and starts after `ICLOUD_B_START_DELAY`
seconds (a `sleep` at the front of B's command wrapper), so the two heavy
passes drift out of phase rather than aligning every cycle.

### Status endpoint

New `homepage-api` endpoint: `GET /api/icloudpd/status/<name>` where `<name>`
is `icloudpd-a` or `icloudpd-b` (validated against an allowlist).

Implementation notes:

- Reuse the existing `_docker_api(path)` helper for
  `GET /containers/<name>/json` (container `State`, `State.Health.Status`,
  `State.StartedAt`).
- Add a sibling helper for the log stream — `GET /containers/<name>/logs?
  stdout=1&stderr=1&tail=250&timestamps=1` returns a raw multiplexed stream,
  not JSON, so it needs its own function that reads the body and strips the
  8-byte frame headers.
- Classification (first match wins, scanning newest lines first):

  | status          | trigger in recent logs / state                                            |
  |-----------------|---------------------------------------------------------------------------|
  | `down`          | container not running / not found                                        |
  | `drive_missing` | wrapper's "backup drive not mounted or wrong drive" line; or unhealthy   |
  | `auth_required` | MFA / two-factor / "Password is required" / "Invalid authentication token" / login failure |
  | `syncing`       | a "Downloading" / in-progress line more recent than the last completion  |
  | `ok`            | a recent completion line ("All photos have been downloaded" / iteration complete), timestamp captured |
  | `unknown`       | none of the above                                                       |

  Exact log-string matches to be finalised against real output from the pinned
  image during implementation.

- Response shape:

  ```json
  {
    "name": "icloudpd-a",
    "status": "ok",
    "statusLabel": "OK",
    "lastSync": "2026-09-06T04:15:00Z",
    "lastSyncRelative": "3 hours ago",
    "message": "All photos downloaded"
  }
  ```

  `statusLabel` is a short human string per status (`OK`, `Syncing`,
  `Re-auth needed`, `Drive not mounted`, `Stopped`, `Unknown`). No emoji.

- Errors talking to the Docker socket return `status: "unknown"` with a
  `message`, HTTP 200 (consistent with `/api/docker/status`).

### Homepage dashboard

`config/homepage/services-template.yaml` gets a new top-level **Backups**
group with two entries:

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
        # same, with icloud-b / icloudpd-b
```

(Confirm the internal `homepage-api` port — the compose file exposes `5000`,
`app.py`'s `__main__` uses `5200`; match whatever the other widgets already
use, which is `5000`.)

`docker-compose.dashboard.yml` passes two new vars to the homepage container:

```yaml
HOMEPAGE_VAR_ICLOUD_A_LABEL: ${ICLOUD_A_LABEL:-Photos A}
HOMEPAGE_VAR_ICLOUD_B_LABEL: ${ICLOUD_B_LABEL:-Photos B}
```

### Makefile

- Add `docker-compose.photos.yml` to the `COMPOSE` variable (and the header
  comment block).
- Add `logs-icloudpd` target: `@$(COMPOSE) logs -f icloudpd-a icloudpd-b`.

### Documentation

- New `docs/icloud-photos-backup.md`:
  - fstab setup (mount by UUID, `nofail`), creating the sentinel file, setting
    `ICLOUD_BACKUP_DRIVE_ID`.
  - First-run authentication: `make start`, open `https://icloud-a.${DOMAIN}`,
    enter Apple ID password + 2FA code in the web UI; repeat for B.
  - The ~2-month re-auth routine: you get an email; open the web UI URL; enter
    the new code.
  - Drive replacement procedure.
  - How to read the dashboard status tile.
- `SERVICES.md`: add both services (table row + section), including the
  pinned image version.
- `README.md`: mention the photo-backup services where other services are
  listed.
- `.env.example`: the variable block above.

## What this protects against (and what it does not)

icloudpd runs **download-only**. It downloads anything present in iCloud that
is not already on the drive and never modifies or removes existing local
files. The `--auto-delete` and `--delete-after-download` flags are
deliberately **not** used and must never be added — with them, deleting a
photo in iCloud would delete it from the backup too.

Protects against:

- Accidental deletion of photos in iCloud (the backup copy remains).
- Apple account lockout, loss, or cloud-side library corruption.

Does **not** protect against:

- **Point-in-time gaps.** The backup is additive, not a snapshot. A photo
  deleted in iCloud before icloudpd ever downloaded it is never captured.
  With continuous ~6h cycles this window is small but real.
- **Loss of the drive itself.** One external drive is a single copy — drive
  failure, theft, filesystem corruption, ransomware, or an accidental delete
  on the drive loses the backup. This is not a 3-2-1 backup.
  Filesystem snapshots (btrfs/ZFS/rsnapshot) are the usual mitigation but are
  out of scope here (the server is too small); a second rotated drive is the
  practical option if stronger durability is wanted later.

This is documented in `docs/icloud-photos-backup.md` for the operator.

## Testing

- `make validate` — compose config parses with the new file.
- `homepage-api` pytest: new tests in `tests/test_app.py` covering the status
  endpoint for each classification (`ok`, `syncing`, `auth_required`,
  `drive_missing`, `down`, `unknown`) with `_docker_api` and the log helper
  mocked, plus the name-allowlist rejection path.
- icloudpd itself runs only on the server (needs Apple credentials). The doc
  covers manual first-run verification: containers reach `ok` on the dashboard
  after the first successful sync.

## Risks / open items

- icloudpd flag names and log strings vary between releases; both are pinned
  down against the chosen image version during implementation, not assumed.
- The web UI port for the pinned version must be confirmed (assumed `8080`).
- If the web UI cannot be limited to one account per container cleanly, fall
  back to `--mfa-provider` console + a documented `docker exec` re-auth, and
  drop the Traefik routes. (Preference remains the web UI.)
