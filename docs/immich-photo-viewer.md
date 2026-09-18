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
`admin-secure-no-ratelimit` — Immich's SPA loads too many assets at once for
the rate-limited variant, same as AdGuard/Grafana/Homepage). The first visit
prompts you to create the admin account —
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

## Hardware acceleration

`immich-server` and `immich-machine-learning` are configured to use the
server's integrated GPU (`/dev/dri`) for video transcoding and ML
inference. Verify it exists before deploying:

```bash
ls -la /dev/dri
```

If `/dev/dri` is missing, fall back to CPU-only:

1. In `docker-compose.immich.yml`, remove the `devices: [/dev/dri:/dev/dri]`
   block from `immich-server`.
2. On `immich-machine-learning`, remove `devices:`, `device_cgroup_rules:`,
   and the `/dev/bus/usb` volume line, and drop the `-openvino` suffix from
   its image tag (falls back to the plain CPU image).
3. Redeploy. ML inference and video transcoding will be slower but
   functionally identical.

## Enabling machine learning later

Immediately after creating the admin account and BEFORE registering the
external libraries, check **Administration → Machine Learning**. If Smart
Search or Facial Recognition are already enabled and you don't want them
running against the full backlog yet, disable them there first — then
register the libraries.

Smart search (search by photo content) and facial recognition can be turned
on or off at any time: **Administration → Machine Learning → enable/disable
Smart Search / Facial Recognition**. This takes effect immediately — no
redeploy needed, since the `immich-machine-learning` container has been
running since first setup. Expect the initial indexing pass over the
existing backlog to take a while on this hardware (no dedicated GPU,
CPU-bound ML inference via OpenVINO acceleration on the integrated GPU
helps but this is still a background job, not instant).

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
