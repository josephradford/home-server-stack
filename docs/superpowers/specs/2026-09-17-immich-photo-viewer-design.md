# Immich Photo Viewer — Design

**Date:** 2026-09-17
**Status:** Approved for planning

## Problem

`icloudpd` (see `docs/icloud-photos-backup.md`) backs up two iCloud photo
libraries to `/mnt/photos-backup/account-a` and `/account-b`, but there is no
way to browse them — just a folder of files organized by year/month. Add a
self-hosted gallery/viewer over that existing backup.

## Hardware context

Server: HP ProDesk 600 G3 Mini, Intel i5-7600T (4 cores, 2.8GHz, no
hyperthreading, integrated HD 630 graphics with Quick Sync), 16GB RAM
(currently ~2.5GB used, ~12GB free across the existing stack), 1TB SSD as
the OS/Docker root disk, plus the separate ext4 external drive for the photo
backups themselves. No dedicated GPU.

## Non-goals

- Not a replacement for icloudpd or the backup mechanism — Immich is a
  read-only viewer/organizer layered on top of what icloudpd already
  manages, not a second backup path.
- Not importing/duplicating the photo files onto the SSD.
- Not exposing Immich outside the LAN/VPN.
- Not enabling face recognition / smart search by default — the container
  that provides them is deployed, but the feature stays off until turned on
  later in Immich's own admin settings (a runtime toggle, not a redeploy).

## Approach

### Services

New `docker-compose.immich.yml`, four services, following Immich's own
reference compose structure (`immich-app/immich`, pinned to `v3.2.2`):

| Service | Image | Purpose |
|---|---|---|
| `immich-server` | `ghcr.io/immich-app/immich-server:v3.2.2` | API, web UI, job orchestration |
| `immich-machine-learning` | `ghcr.io/immich-app/immich-machine-learning:v3.2.2-openvino` | Face/CLIP models — deployed, feature left off |
| `immich-postgres` | `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0` (pinned digest, per upstream) | Metadata, embeddings |
| `immich-redis` | `docker.io/valkey/valkey:9` (pinned digest, per upstream) | Job queue |

All four on the `homeserver` network (`external: true`, matching the pattern
established for `docker-compose.photos.yml` and `docker-compose.location.yml`
— see the icloudpd merge spec for why: it must match whichever file is last
in the Makefile's `COMPOSE` list, verified at implementation time).

### External library (read-only)

`/mnt/photos-backup` is bind-mounted **read-only** into `immich-server` (and
`immich-machine-learning`, which needs local file access for inference
rather than round-tripping bytes through the API — confirmed against
upstream's own compose/docs at implementation time, since this detail
varies by Immich version):

```yaml
volumes:
  - /mnt/photos-backup:/mnt/photos-backup:ro
```

After first login, an admin registers `/mnt/photos-backup/account-a` and
`/mnt/photos-backup/account-b` as two **External Libraries** (Administration
→ External Libraries in Immich's own UI — this is a one-time manual step,
not automatable via compose or `.env`, same category of first-run action as
icloudpd's own web-UI authentication). Read-only means Immich indexes and
displays these photos but cannot delete or modify the originals through its
own UI — icloudpd remains the only writer to that drive.

Immich's own managed storage (`UPLOAD_LOCATION` — thumbnails, transcoded
video previews, and any future non-external uploads) is a separate bind
mount on the OS SSD: `./data/immich/upload`. This does **not** duplicate the
full-size originals; it holds derived/generated files only, which is
materially smaller than the source library.

### Machine learning / hardware acceleration

`immich-machine-learning` uses the `-openvino` image variant to use the
i5-7600T's integrated GPU (Quick Sync-capable HD 630) for inference instead
of pure CPU, with `/dev/dri` passed through:

```yaml
devices:
  - /dev/dri:/dev/dri
```

Immich's official compose ships this as an `extends:` reference to a
separate `hwaccel.ml.yml` fragment (and, for video transcoding
specifically, `hwaccel.transcoding.yml` on `immich-server`) rather than
inlining device blocks directly — the implementation should pull in
whichever pattern matches the pinned `v3.2.2` release rather than
hand-rolling it, to stay consistent with upstream's own tested
configuration.

Smart search and facial recognition stay **off** by default (Immich's own
default) — enabling them later is Administration → Machine Learning →
toggle, no redeploy. Video transcoding hardware acceleration (separate from
ML) can also use Quick Sync via the same `/dev/dri` passthrough on
`immich-server`.

### Data persistence

Under `./data/immich/`, following the stack's existing bind-mount
convention:
- `./data/immich/postgres` — database
- `./data/immich/upload` — Immich-managed derived files (thumbnails,
  transcodes)
- `./data/immich/model-cache` — downloaded ML models (only grows once ML is
  actually enabled)

### Traefik / access

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.immich.rule=Host(`immich.${DOMAIN}`)"
  - "traefik.http.routers.immich.entrypoints=websecure"
  - "traefik.http.routers.immich.tls=true"
  - "traefik.http.services.immich.loadbalancer.server.port=2283"
  - "traefik.http.routers.immich.middlewares=admin-secure"
```

Same LAN/VPN-only pattern as every other admin service in this stack —
`https://immich.${DOMAIN}`, gated by the `admin-secure` middleware
(RFC1918 + VPN allowlist), no public exposure.

### Env vars (`.env.example`)

```
# Immich photo viewer — reads icloudpd's backups as a read-only external
# library. See docs/immich-photo-viewer.md for first-run setup (creating an
# admin account, registering the external libraries).
IMMICH_VERSION=v3.2.2
IMMICH_DB_PASSWORD=change_me_immich_db_password
```

No account-identifying values needed — Immich's own admin account is
created through its first-run web UI, not env-configured, and the external
library paths are fixed (`/mnt/photos-backup/account-a`, `account-b`),
already generic.

### Homepage dashboard

A single entry alongside icloudpd's tile, no custom status widget needed —
Immich has a standard container-health-based entry like most other services
in this stack (`showStats: true`, no `customapi` widget):

```yaml
- Immich:
    icon: immich.png
    href: https://immich.{{HOMEPAGE_VAR_DOMAIN}}
    description: Photo library viewer
    container: immich-server
    server: my-docker
    showStats: true
```

### Makefile / docs

- Add `docker-compose.immich.yml` to `COMPOSE`.
- `logs-immich` target: `@$(COMPOSE) logs -f immich-server immich-machine-learning`.
- New `docs/immich-photo-viewer.md`: first-run admin account creation,
  registering the two external libraries (paths, read-only), how to enable
  ML later, note that Immich is a viewer only — icloudpd remains the sole
  writer to the backup drive.
- `SERVICES.md` — new entry + Quick Reference row.

## Testing

- `make validate` for the new compose file.
- No homepage-api code changes — nothing to unit test there.
- Manual, on the server (the only way to verify an external system like
  this): bring the four containers up, confirm `immich-postgres` and
  `immich-redis` reach healthy first (server has a `depends_on` ordering on
  them), complete first-run admin setup, register both external libraries
  read-only, confirm photos are visible and confirm a delete attempt inside
  Immich on an external-library asset is refused (proving read-only holds).

## Risks / open items

- **Exact hwaccel compose fragments** (`hwaccel.ml.yml` /
  `hwaccel.transcoding.yml`) must be pulled from the actual `v3.2.2` release
  tag at implementation time rather than assumed — Immich's hardware
  acceleration wiring has changed across versions.
- **Whether `immich-machine-learning` needs the library bind-mounted
  directly** (vs. only `immich-server` needing it, with ML receiving bytes
  over the internal API) should be confirmed against the pinned version's
  own compose file, not assumed from general docs.
- Initial ML indexing of the existing backlog (once enabled) will be slow on
  this CPU — expected and acceptable, not a defect, but worth setting
  expectations for in the doc.
- First-run steps (admin account, external library registration) are
  manual and cannot be scripted through compose/env — same category as
  icloudpd's own web-UI first-run auth.
