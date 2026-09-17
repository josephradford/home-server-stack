# Immich Photo Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Immich as a self-hosted, read-only photo viewer over the existing icloudpd backups, reachable only on the LAN/VPN, with the machine-learning container deployed but its features left off until enabled later in Immich's own admin UI.

**Architecture:** New `docker-compose.immich.yml` with four services (`immich-server`, `immich-machine-learning`, `immich-postgres`, `immich-redis`), matching upstream Immich's own reference compose (pinned `v3.2.2`) adapted to this repo's conventions — bind mounts under `./data/immich/`, `homeserver` external network, `admin-secure` Traefik middleware. `/mnt/photos-backup` is bind-mounted read-only into `immich-server` and `immich-machine-learning`; the external libraries themselves are registered through Immich's own first-run admin UI, not through compose or `.env` (same category of manual step as icloudpd's own web-UI authentication).

**Tech Stack:** Docker Compose, `ghcr.io/immich-app/immich-server:v3.2.2`, `ghcr.io/immich-app/immich-machine-learning:v3.2.2-openvino`, `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`, `valkey:9`.

**Spec:** `docs/superpowers/specs/2026-09-17-immich-photo-viewer-design.md`

## Global Constraints

- **Read-only external library.** `/mnt/photos-backup` is mounted `:ro` into both `immich-server` and `immich-machine-learning` — Immich must never be able to write to, delete from, or modify the icloudpd backup drive. icloudpd remains the sole writer.
- **No duplication of originals onto the SSD.** Immich's own managed storage (`./data/immich/upload`) holds only derived files (thumbnails, transcoded previews) — never a copy of the full-size photos, which stay on the external drive as an External Library, not an imported library.
- **ML container deployed, feature left off.** `immich-machine-learning` runs from day one (openvino-accelerated), but smart search / facial recognition stay at Immich's own default (off) — enabling them later is an in-app admin toggle, not a redeploy.
- **LAN/VPN-only access.** `https://immich.${DOMAIN}` behind the `admin-secure` Traefik middleware — same pattern as every other admin service in this stack. No public exposure.
- **Pinned versions**: `IMMICH_VERSION=v3.2.2` for `immich-server` and `immich-machine-learning`; `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:bcf63357191b76a916ae5eb93464d65c07511da41e3bf7a8416db519b40b1c23` and `docker.io/valkey/valkey:9@sha256:70739f85ad2ee01a726a965584a0f94895f01b0c60b3cc8b0aeef11eaa6888cf` for the two data services (exact digests, matching upstream's own pinned compose for this release — confirmed by fetching `docker/docker-compose.yml` at the `v3.2.2` tag directly).
- **No identifying data in committed code.** Only the DB password placeholder and version pin go in `.env.example`; no account/library data is config-driven (Immich's own admin account and external libraries are created through its web UI on first run).
- **Data persistence follows this repo's convention**: all state under `./data/immich/` as bind mounts (not upstream's default named `model-cache` volume or relative `./library`/`./postgres` paths).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `docker-compose.immich.yml` (create) | Four Immich services. |
| `.env.example` (modify) | `IMMICH_VERSION`, `IMMICH_DB_PASSWORD` placeholders. |
| `Makefile` (modify) | Add `docker-compose.immich.yml` to `COMPOSE`; add `logs-immich` target. |
| `config/homepage/services-template.yaml` (modify) | New Immich entry (plain container-health tile, no custom widget). |
| `docs/immich-photo-viewer.md` (create) | First-run setup: admin account, registering the two external libraries, enabling ML later. |
| `SERVICES.md` (modify) | New entry + Quick Reference row. |

No `homepage-api` changes — Immich uses a standard `showStats: true` Homepage entry like most services in this stack, no custom status endpoint.

---

## Task 1: Compose file, environment, Makefile, data directories

**Files:**
- Create: `docker-compose.immich.yml`
- Modify: `.env.example` (append a new block at the end)
- Modify: `Makefile` (header comment, `COMPOSE` var, new `logs-immich` target)
- Create (empty, git-tracked): `data/immich/upload/.gitkeep`, `data/immich/postgres/.gitkeep`, `data/immich/model-cache/.gitkeep`

**Interfaces:**
- Produces: containers `immich-server` (port 2283, Traefik host `immich`), `immich-machine-learning`, `immich-postgres`, `immich-redis`, all on the `homeserver` network; env vars `IMMICH_VERSION`, `IMMICH_DB_PASSWORD` consumed only within this file.

- [ ] **Step 1: Write `docker-compose.immich.yml`**

```yaml
# Immich — self-hosted photo viewer reading icloudpd's backups as a
# read-only external library. See docs/immich-photo-viewer.md for the
# first-run admin setup (Immich has no compose/env-driven account creation).
#
# /mnt/photos-backup is mounted read-only into immich-server and
# immich-machine-learning — Immich must never write to the backup drive;
# icloudpd remains the sole writer. Immich's own managed storage
# (./data/immich/upload) holds only derived files (thumbnails, transcoded
# previews), never a copy of the originals.

services:
  immich-server:
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-v3.2.2}
    container_name: immich-server
    restart: unless-stopped
    networks:
      - homeserver
    environment:
      TZ: ${TIMEZONE:-UTC}
      DB_HOSTNAME: immich-postgres
      DB_USERNAME: postgres
      DB_DATABASE_NAME: immich
      DB_PASSWORD: ${IMMICH_DB_PASSWORD}
      REDIS_HOSTNAME: immich-redis
    volumes:
      - ./data/immich/upload:/data
      - /mnt/photos-backup:/mnt/photos-backup:ro
      - /etc/localtime:/etc/localtime:ro
    # Quick Sync hardware-accelerated video transcoding (separate from ML
    # inference below) — uses the same integrated GPU.
    devices:
      - /dev/dri:/dev/dri
    depends_on:
      - immich-redis
      - immich-postgres
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.immich.rule=Host(`immich.${DOMAIN}`)"
      - "traefik.http.routers.immich.entrypoints=websecure"
      - "traefik.http.routers.immich.tls=true"
      - "traefik.http.services.immich.loadbalancer.server.port=2283"
      - "traefik.http.routers.immich.middlewares=admin-secure"

  immich-machine-learning:
    # -openvino uses the server's integrated GPU (Quick Sync-capable HD 630)
    # for inference instead of pure CPU. Deployed so ML features can be
    # turned on later purely via Immich's admin UI, with zero redeploy.
    image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-v3.2.2}-openvino
    container_name: immich-machine-learning
    restart: unless-stopped
    networks:
      - homeserver
    environment:
      TZ: ${TIMEZONE:-UTC}
    volumes:
      - ./data/immich/model-cache:/cache
      - /mnt/photos-backup:/mnt/photos-backup:ro
      - /dev/bus/usb:/dev/bus/usb
    device_cgroup_rules:
      - 'c 189:* rmw'
    devices:
      - /dev/dri:/dev/dri

  immich-redis:
    image: docker.io/valkey/valkey:9@sha256:70739f85ad2ee01a726a965584a0f94895f01b0c60b3cc8b0aeef11eaa6888cf
    container_name: immich-redis
    restart: unless-stopped
    networks:
      - homeserver
    healthcheck:
      test: ["CMD-SHELL", "redis-cli ping | grep -q PONG || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  immich-postgres:
    image: ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:bcf63357191b76a916ae5eb93464d65c07511da41e3bf7a8416db519b40b1c23
    container_name: immich-postgres
    restart: unless-stopped
    networks:
      - homeserver
    environment:
      POSTGRES_PASSWORD: ${IMMICH_DB_PASSWORD}
      POSTGRES_USER: postgres
      POSTGRES_DB: immich
      POSTGRES_INITDB_ARGS: '--data-checksums'
    volumes:
      - ./data/immich/postgres:/var/lib/postgresql/data
    shm_size: 128mb

networks:
  homeserver:
    external: true
    name: home-server-stack_homeserver
```

Notes for the implementer:
- `DB_HOSTNAME: immich-postgres` and `REDIS_HOSTNAME: immich-redis` are required overrides — Immich's own defaults (`database`, `redis`) assume upstream's default service names, which this file deliberately renames for clarity/collision-avoidance, matching the prefixed naming this repo already uses for multi-container features (compare `icloudpd-a`/`icloudpd-b` before their merge).
- No explicit `healthcheck:` on `immich-server` or `immich-machine-learning` — both images ship their own `HEALTHCHECK` directive (upstream's own compose sets `healthcheck: {disable: false}`, which is the Compose default already); Docker Compose uses the image's built-in check unless overridden, so omitting the key here is equivalent and simpler.
- The `/dev/dri`, `device_cgroup_rules`, and `/dev/bus/usb` values on `immich-machine-learning` are the exact `openvino` backend block from upstream's `docker/hwaccel.ml.yml` at the `v3.2.2` tag, inlined directly rather than using Compose's `extends:` mechanism — this repo's other multi-file compose setups only compose at the Makefile `-f` level, never within a single service, so inlining matches existing convention.
- If `/dev/dri` doesn't exist on the server (no `/dev/dri` device node — shouldn't happen on this hardware, but confirm), remove the `devices:`/`device_cgroup_rules:` block from `immich-machine-learning` and drop the `-openvino` suffix from its image tag (falling back to the plain CPU image) as a fallback; same for `immich-server`'s `/dev/dri` line if Quick Sync transcoding isn't available. Verify `/dev/dri` exists on the server before relying on this — a server-verify item, not something to detect from this checkout.

- [ ] **Step 2: Verify the compose file renders**

Run: `docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml config --quiet`

Expected: exits 0. Requires `IMMICH_DB_PASSWORD` to exist in `.env` (Step 3) — set a throwaway value locally if needed. If Docker isn't available in your environment, note it as a server-verify item (same limitation every prior compose task in this repo's history has hit on this Mac-only dev environment).

- [ ] **Step 3: Append the `.env.example` block**

```bash
# =============================================================================
# Immich — Photo Viewer
# =============================================================================
# Self-hosted photo gallery reading icloudpd's backups as a read-only
# external library. See docs/immich-photo-viewer.md for first-run setup
# (admin account creation and external library registration happen in
# Immich's own web UI, not here).

IMMICH_VERSION=v3.2.2
IMMICH_DB_PASSWORD=change_me_immich_db_password
```

- [ ] **Step 4: Create the data directory placeholders**

```bash
mkdir -p data/immich/upload data/immich/postgres data/immich/model-cache
touch data/immich/upload/.gitkeep data/immich/postgres/.gitkeep data/immich/model-cache/.gitkeep
```

- [ ] **Step 5: Update the Makefile**

In the header comment block (near the other compose-file descriptions), add:

```make
# - docker-compose.immich.yml: Immich photo viewer (immich-server, immich-machine-learning, immich-postgres, immich-redis)
```

Add `docker-compose.immich.yml` to the `COMPOSE` variable:

```make
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml
```

(Append after whichever files are currently last in the list — check the file's current state before editing, since the icloudpd merge plan may have already changed this line's ordering.)

Add a logs target, next to `logs-icloudpd`:

```make
logs-immich:
	@$(COMPOSE) logs -f immich-server immich-machine-learning
```

Add `logs-immich` to the `.PHONY` line that lists the other `logs-*` targets.

- [ ] **Step 6: Validate**

Run: `make validate`
Expected: PASS if Docker is available; otherwise server-verify (per Step 2).

- [ ] **Step 7: Commit**

```bash
git add docker-compose.immich.yml .env.example Makefile data/immich/upload/.gitkeep data/immich/postgres/.gitkeep data/immich/model-cache/.gitkeep
git commit -m "feat: add Immich photo viewer over icloudpd backups"
```

---

## Task 2: Homepage dashboard entry

**Files:**
- Modify: `config/homepage/services-template.yaml`

**Interfaces:**
- Consumes: container `immich-server` (Task 1).

- [ ] **Step 1: Add the Immich entry**

Add a new entry to the `- Services:` group in `config/homepage/services-template.yaml`, alongside the other user-facing services (follow the file's existing indentation and structure for a plain container-health entry — see the `n8n` or `AdGuard Home` entries under `Core Services` for the pattern of a service with `href`/`container`/`server`/`showStats` and no `widget:` block):

```yaml
      - Immich:
          icon: mdi-image-multiple
          href: https://immich.{{HOMEPAGE_VAR_DOMAIN}}
          description: Photo library viewer
          container: immich-server
          server: my-docker
          showStats: true
```

Place it under whichever subgroup (`Core Services` or a new subgroup) best matches the file's existing organization — read the current `- Services:` structure before deciding, since this repo groups services by role (Core Services, Monitoring, Dashboard, Network & Security, Location) and Immich is a new kind of thing (a viewer, not infrastructure) that may warrant its own subgroup consistent with how `Backups` became its own top-level group in the icloudpd feature.

- [ ] **Step 2: Lint the YAML**

Run: `python -c "import yaml,sys; yaml.safe_load(open('config/homepage/services-template.yaml'))"`
Expected: no exception, or note as server-verify if `yaml` isn't importable locally.

- [ ] **Step 3: Validate compose**

Run: `make validate`
Expected: PASS (unaffected by this YAML-only change, but confirms nothing else broke).

- [ ] **Step 4: Commit**

```bash
git add config/homepage/services-template.yaml
git commit -m "feat: add Immich to homepage dashboard"
```

---

## Task 3: Documentation

**Files:**
- Create: `docs/immich-photo-viewer.md`
- Modify: `SERVICES.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Write `docs/immich-photo-viewer.md`**

````markdown
# Immich Photo Viewer

Self-hosted photo gallery (`immich-server`, `immich-machine-learning`,
`immich-postgres`, `immich-redis`) reading icloudpd's backups as a
read-only external library. Defined in `docker-compose.immich.yml`.

Immich is a **viewer/organizer only** — it never writes to
`/mnt/photos-backup`. icloudpd remains the sole writer to that drive.

## First-run setup

### 1. Start the containers

```bash
make validate && make update
```

`immich-postgres` and `immich-redis` come up first; `immich-server` and
`immich-machine-learning` depend on them.

### 2. Create the admin account

Open `https://immich.${DOMAIN}` (home network / VPN only, behind
`admin-secure`). The first visit prompts you to create the admin account —
this is entirely in-app; nothing is configured through `.env` or compose for
this step.

### 3. Register the external libraries (read-only)

In Immich: **Administration → External Libraries → Create Library**.

Create two libraries, one per account, each pointed at the path as it
appears *inside the container* (not the host path):

- `/mnt/photos-backup/account-a`
- `/mnt/photos-backup/account-b`

Leave these as read-only external libraries (the default for a library
pointed at a path mounted `:ro` — Immich will refuse to modify files it
can't write to). Trigger a scan; Immich indexes the existing files without
copying them anywhere.

## Enabling machine learning later

Smart search (search by photo content) and facial recognition are deployed
but **off by default**. To turn them on: **Administration → Machine
Learning → enable Smart Search / Facial Recognition**. This takes effect
immediately — no redeploy needed, since the `immich-machine-learning`
container has been running since first setup. Expect the initial indexing
pass over the existing backlog to take a while on this hardware (no
dedicated GPU, CPU-bound ML inference via OpenVINO acceleration on the
integrated GPU helps but this is still a background job, not instant).

## What this does and doesn't do

- **Does:** browse, search (once ML is enabled), organize into albums, view
  timeline — all read-only against the icloudpd backup.
- **Does not:** back up anything — icloudpd is still the only backup
  mechanism. Does not delete, modify, or duplicate the original files.
- Immich's own storage (`./data/immich/upload`) holds only thumbnails and
  transcoded video previews it generates — not copies of your photos.

## Logs

```bash
make logs-immich
```
````

- [ ] **Step 2: Update `SERVICES.md`**

Add a new section (placement depends on how the file is organized at the
time — read it first; a reasonable location is near the icloudpd section,
since both relate to photos, or under whatever service category the file
uses for user-facing viewer/media apps):

```markdown
#### Immich (Photo Viewer)

Self-hosted photo gallery (`immich-server`, `immich-machine-learning`,
`immich-postgres`, `immich-redis`) reading icloudpd's backups as a
read-only external library — never writes to the backup drive. Access:
`https://immich.${DOMAIN}` (home/VPN only). Machine learning (smart
search, face recognition) is deployed but off by default — enable later in
Administration → Machine Learning, no redeploy needed. Full setup:
`docs/immich-photo-viewer.md`.
```

Add a Quick Reference row:

```markdown
| Immich | https://immich.${DOMAIN} | N/A |
```

- [ ] **Step 3: Commit**

```bash
git add docs/immich-photo-viewer.md SERVICES.md
git commit -m "docs: document immich photo viewer setup"
```

---

## Final verification (after all tasks)

- [ ] `make validate` passes.
- [ ] `git log --oneline` shows 3 clean commits (plus the design-spec commit).
- [ ] Grep check for identifying data: manual read confirms no real paths/credentials were introduced (only the `change_me_immich_db_password` placeholder).

## Server migration (manual, after merge — cannot be verified any other way)

1. Confirm `/dev/dri` exists on the server (`ls -la /dev/dri`) before deploying — if it doesn't, adjust the compose file per Task 1 Step 1's fallback note before deploying, rather than deploying and discovering it broken.
2. Deploy the branch, `make validate && make update`.
3. Confirm `immich-postgres` and `immich-redis` reach healthy before `immich-server` starts serving (`make status` / `docker ps`).
4. Open `https://immich.${DOMAIN}`, create the admin account.
5. Register both external libraries read-only (`/mnt/photos-backup/account-a`, `/mnt/photos-backup/account-b`), trigger a scan, confirm photos appear.
6. Confirm read-only actually holds: attempt to delete one asset from an external library inside Immich's UI and confirm it's refused (or at minimum confirm the file is untouched on disk afterward) — this is the one thing in this feature that would be a real problem if it silently didn't work.
7. Confirm the Homepage entry shows `immich-server` as healthy.
8. Leave machine learning off unless/until you decide to enable it — no action needed here.
