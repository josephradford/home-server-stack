# iCloud Photos Backup — Merge to Single Container

**Date:** 2026-09-17
**Status:** Approved for planning

## Problem

The iCloud photos backup feature (`docs/superpowers/specs/2026-09-06-icloud-photos-backup-design.md`)
shipped with two `icloudpd` containers, one per Apple account, each with its
own env-driven watch interval and a manual start-delay stagger on the second
account to avoid simultaneous disk I/O on the external HDD.

icloudpd natively supports multiple accounts in a single process via
repeated `--username`/`--directory` pairs (added in icloudpd 1.32.0; we run
1.32.3). Processing is sequential — one account at a time, never
concurrent — which makes the stagger workaround in the current two-container
design unnecessary. Consolidating to one container also halves the running
container count, Traefik routes, and compose service definitions for this
feature.

This spec covers restructuring the already-deployed two-container setup into
one, including the migration of the live test-server deployment (one account,
`icloudpd-a`, already has a working authenticated session and ~969MB
synced).

## Non-goals

- No change to the drive guard, healthcheck design, or sentinel-file mechanism
  — these are container/process-level and apply unchanged to the merged
  container.
- No change to what icloudpd protects against / doesn't (still download-only,
  still a single point of failure on one drive).
- No re-architecting of Homepage's Backups group beyond dropping from two
  entries to one.
- Not migrating existing session/cookie state — this is a deliberate fresh
  start (see Migration).

## Approach

### Compose structure

`docker-compose.photos.yml` collapses from two services sharing a YAML
anchor (`icloudpd-a`, `icloudpd-b`) to **one service**, `icloudpd`:

- `container_name: icloudpd`
- Single healthcheck (drive sentinel test, unchanged from the current
  per-container version).
- Single `command` wrapper: the existing startup drive-guard check + 5-minute
  background re-check loop (unchanged logic), followed by one `exec
  /app/icloudpd` invocation covering both accounts.
- Single Traefik router: `icloud.${DOMAIN}` → container port 8080,
  `admin-secure` middleware, TLS — same shape as every other admin-secure
  route in this stack, replacing the two `icloud-a`/`icloud-b` routers.
- Single volume for cookies: `./data/icloudpd/cookies:/cookies` (icloudpd
  documents that `--cookie-directory` is safe to share across accounts —
  session files are named by username internally, so they don't collide).
- The drive volume mount (`${ICLOUD_BACKUP_ROOT}:/drive`) is unchanged; both
  accounts' subdirectories (`account-a`, `account-b`) still live under it.

### Command

Options before the first `--username` are shared defaults (icloudpd's own
convention); each `--username`/`--directory` pair after that scopes to that
account only:

```sh
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
```

The startup drive-guard and the 5-minute mid-run re-check loop wrap this
exactly as they wrap the current per-account commands — unchanged logic,
just guarding one process instead of two.

### Env vars

Removed (staggering no longer applies — one sequential process never
contends with itself):
- `ICLOUD_B_INTERVAL`
- `ICLOUD_B_START_DELAY`

Renamed:
- `ICLOUD_A_INTERVAL` → `ICLOUD_INTERVAL` (governs the single shared watch
  loop covering both accounts)

Removed, replaced:
- `ICLOUD_A_LABEL`, `ICLOUD_B_LABEL` → single `ICLOUD_LABEL` (default
  `"Photo Backups"`), the merged dashboard tile's display name.

Unchanged: `ICLOUD_BACKUP_ROOT`, `ICLOUD_BACKUP_DRIVE_ID`,
`ICLOUD_FOLDER_STRUCTURE`, `ICLOUD_SMTP_HOST/PORT/USERNAME/PASSWORD`,
`ICLOUD_NOTIFICATION_EMAIL`, `ICLOUD_A_USERNAME`/`ICLOUD_A_SUBDIR`,
`ICLOUD_B_USERNAME`/`ICLOUD_B_SUBDIR`.

### Migration (fresh start)

Confirmed with the user: this is a deliberate fresh start for authentication,
not a data migration.

- The two existing containers/services are removed.
- `./data/icloudpd/a/cookies` and `./data/icloudpd/b/cookies` are deleted —
  both accounts re-authenticate (password + 2FA) from scratch via the new
  shared web UI at `https://icloud.${DOMAIN}`.
- **Already-downloaded photos are untouched.** `/mnt/photos-backup/account-a`
  and `/mnt/photos-backup/account-b` are not modified by this migration.
  icloudpd deduplicates against existing files on disk, so re-authenticating
  does not re-download anything already present — only the session resets.
- The two old Traefik hosts (`icloud-a.${DOMAIN}`, `icloud-b.${DOMAIN}`)
  retire; only `icloud.${DOMAIN}` remains.
- Because icloudpd processes accounts sequentially, the web UI is expected to
  prompt for account A first, then (once that completes) prompt for account
  B — not simultaneously. This is inferred from icloudpd's sequential
  per-user log behavior observed in the current deployment
  (`Processing user: <email>` markers appear one account at a time); the
  actual UX will be confirmed live during deployment and is called out as a
  verify-on-deploy item below.

### homepage-api status endpoint

Route simplifies: `GET /api/icloudpd/status/<name>` (2-item allowlist)
becomes `GET /api/icloudpd/status` (no parameter — there is exactly one
target now).

`_classify_icloudpd` keeps its existing container-level checks first,
unchanged:
- not running → `down`
- drive sentinel missing / `health == 'unhealthy'` → `drive_missing`

Below that, the classification becomes account-aware because the log stream
now interleaves both accounts' lines, distinguished only by icloudpd's own
`Processing user: <email>` markers:

1. Split the recent log tail into segments, each segment starting at a
   `Processing user: <email>` line and running to the next such line (or end
   of tail).
2. For each account that appears, classify its **latest** segment using the
   existing newest-first marker logic (auth markers / done markers /
   progress markers), unchanged from the per-container version.
3. Combine the per-account results into one output using severity order,
   worst wins: `auth_required` > `syncing` > `unknown` > `ok`.

This is deliberately more work than a naive "scan the whole tail for any
matching marker" — that naive approach would resurface a long-resolved
problem from one account (e.g. an auth error from days ago still inside the
tail window) as if it were current, or mask a genuinely broken account
behind the other account's more recent successful activity. Segmenting by
account first, then taking each account's own newest-first result, avoids
both failure modes. (This mirrors the fix already applied to the
single-account classifier for the equivalent staleness bug — see the final
review in the original feature's implementation plan.)

If icloudpd's log ever includes a account-level line for the drive-guard
message inside a `Processing user:` segment (it won't — the drive guard runs
before `exec icloudpd`, so that log line always precedes any
`Processing user:` marker), no special handling is needed; the container-level
check already catches it first.

### Homepage dashboard

`services-template.yaml`'s Backups group drops from two entries to one:

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

`docker-compose.dashboard.yml` passes `HOMEPAGE_VAR_ICLOUD_LABEL:
${ICLOUD_LABEL:-Photo Backups}` in place of the two per-account label vars.

### Makefile / docs

- `logs-icloudpd` target becomes `@$(COMPOSE) logs -f icloudpd`.
- `docs/icloud-photos-backup.md` rewritten for the single-container flow:
  one web UI URL, sequential per-account auth prompts, shared cookie
  directory, updated `.env` variable list, updated re-auth instructions
  (the dashboard tile and notification email no longer identify which
  account needs re-auth — the doc should say to check `make logs-icloudpd`
  for the specific account if the tile alone isn't enough).
- `SERVICES.md` — single icloudpd entry and Quick Reference row instead of
  two.

## Testing

- `homepage-api` pytest: rewrite `TestIcloudpdStatusEndpoint` for the new
  route shape and the segment-then-worst-of classifier behavior — cases:
  both accounts `ok`, one `auth_required` / other `ok` (worst wins), one
  `syncing` / other `ok`, drive missing short-circuits regardless of
  per-account state, container not running short-circuits.
- `make validate` for the restructured compose file.
- Manual, on the server (cannot be verified any other way): remove the old
  containers, bring up the merged one, confirm both accounts prompt for
  auth through the single web UI, confirm the dashboard tile reaches `OK`
  after both accounts complete a sync pass, confirm existing files under
  `/mnt/photos-backup/account-a` are recognized as already-downloaded
  (no redundant re-fetch) once account A re-authenticates.

## Risks / open items

- **Web UI multi-account prompt UX is unverified from documentation alone**
  (icloudpd's own docs don't describe the sequencing in detail). Confirmed
  live during deployment; if the UX turns out to be confusing or ambiguous
  about which account is being prompted, that becomes a follow-up issue
  rather than a blocker for this merge, since the underlying CLI behavior
  (sequential processing, independent per-account failure handling) is
  documented and confirmed.
- Losing per-account dashboard visibility is a deliberate, explicit
  trade-off the user made in favor of a simpler single tile — not an
  oversight.
