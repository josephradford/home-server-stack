# Ebook Library (Calibre-Web-Automated + Kobo sync)

Self-hosted EPUB/PDF library (`cwa`, Calibre-Web-Automated) at
`https://books.${DOMAIN}`, paired with a `library-digest` sidecar that turns a
curated RSS feed list into one EPUB per day. Defined in
`docker-compose.library.yml`.

A Kobo Clara BW (bought separately) syncs wirelessly from `cwa` over home
Wi-Fi. The Kobo doesn't run WireGuard, so sync only works on the home
network — USB sideloading remains a fallback that always works.

## First-run setup

### 1. Prep data directories

```bash
mkdir -p data/cwa/{config,ingest,library} data/library-digest
chown -R $(id -u):$(id -g) data/cwa data/library-digest
```

### 2. Start the containers

```bash
make validate && make update
```

### 3. Create the CWA admin account and change the password

Open `https://books.${DOMAIN}` (home network / VPN only, behind
`admin-secure-no-ratelimit`). Log in with CWA's documented default admin
credentials (check the [CWA docs](https://github.com/crocodilestick/Calibre-Web-Automated)
for the current default — it has changed across versions) and **change the
password immediately** from the admin panel.

### 4. Enable Kobo Sync

In CWA's admin settings, enable **Kobo Sync** and set the external server URL
to `https://books.${DOMAIN}` (no port).

### 5. Create a Kobo sync token

On your user profile in CWA, create a **Kobo sync token**. This produces an
`api_endpoint` URL — copy it.

### 6. Pair the physical Kobo

1. Plug the Kobo into a computer via USB.
2. Open `.kobo/Kobo/Kobo eReader.conf` on the device and replace the
   `api_endpoint` line with the one from step 5.
3. Eject the device safely.
4. On home Wi-Fi, trigger a sync from the Kobo's menu. Books already in the
   CWA library should start appearing.

### 7. Add real reading feeds

Edit `config/library/feeds.txt` (one RSS URL per line, `#` to comment out).
Any Substack's feed is `https://<name>.substack.com/feed`. This is a curated,
short list by design — the point is a finite nightly batch, not an endless
feed. Changes take effect on the next `library-digest` run (or immediately via
`make library-digest-now`).

## Operating

- `make logs-cwa` / `make logs-library-digest` — tail logs for each container.
- `make library-digest-now` — run the digest immediately instead of waiting
  for the daily cycle (`DIGEST_INTERVAL`, default 86400s, in `.env`).
- Drop an EPUB or PDF directly into `data/cwa/ingest/` at any time — CWA
  imports and clears it within about a minute, independent of the digest job.

## Troubleshooting

- **Digest writes nothing:** check `make logs-library-digest` — a feed URL
  that 404s or times out is skipped silently per-feed but should still show
  up in feedparser's output; verify the URL resolves with
  `curl -sI <feed-url>`.
- **A daily EPUB never triggers a re-import:** confirm `data/cwa/ingest`'s
  ownership matches CWA's `PUID`/`PGID` (both containers must agree — see
  `DIGEST_PUID`/`DIGEST_PGID` in `docker-compose.library.yml`); a file CWA
  can't read/delete will sit in the ingest folder forever.
- **Kobo won't sync:** re-check the `api_endpoint` line in
  `Kobo eReader.conf` — a typo there is the most common cause. The Kobo must
  be on the same home Wi-Fi as the server (it has no VPN client).
- **CWA unreachable from off-network:** expected — `admin-secure-no-ratelimit`
  restricts it to LAN/VPN IPs. This is intentional; nothing to fix.

## Known limitations

- Remote images embedded in a digest post are left as remote `<img>` URLs —
  they won't render once the EPUB is on an offline Kobo.
- Paid Substack posts appear only as their free RSS preview.
- No cross-feed de-duplication by title — two feeds covering the same story
  can both appear in one digest.
- Out of scope for now (see the design brief): paid-Substack mailbox
  ingestion, a PDF-reflow pipeline (OCRmyPDF / k2pdfopt / Marker), and any
  public exposure of the library.
