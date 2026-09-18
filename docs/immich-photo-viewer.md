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
