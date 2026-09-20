# Ebook Library (Kobo-synced) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-hosted ebook library (Calibre-Web-Automated, "CWA") reachable at `books.${DOMAIN}`, with a daily RSS-to-EPUB digest job that drops curated reading into CWA's ingest folder, so a Kobo Clara BW can sync it over home Wi-Fi.

**Architecture:** A new compose file (`docker-compose.library.yml`) adds two services on the existing `homeserver` external network: `cwa` (Calibre-Web-Automated, Traefik-routed, LAN/VPN only) and `library-digest` (a lightweight Python loop container that polls `config/library/feeds.txt`, converts new posts into one EPUB per day via `scripts/library/digest.py`, and writes it to the shared `data/cwa/ingest/` bind mount that CWA watches). No new external dependencies beyond the two pinned images; state (`seen.json`, the CWA library/config) lives under `./data/` like every other service.

**Tech Stack:** Docker Compose, Calibre-Web-Automated (`ghcr.io/crocodilestick/calibre-web-automated`), Python 3.12 (`feedparser`, `ebooklib`), Traefik labels, Makefile, Homepage dashboard config.

**Spec:** `/Users/joeradford/Downloads/EBOOK-LIBRARY-HANDOFF.md` (design brief this plan implements — sections 3/4 are the source of truth for conventions and file content; deviations are noted per-task below).

## Global Constraints

- Follow the repo's existing per-topic compose file split; add `docker-compose.library.yml`, do not fold into an existing file (matches `docker-compose.photos.yml` / `.immich.yml` precedent).
- Shared network: reference as `external: true`, `name: home-server-stack_homeserver` (exact string used by every other compose file).
- Traefik labels: `admin-secure-no-ratelimit` middleware for `cwa` (Kobo sync is chatty — same reasoning the brief gives), wildcard cert via file provider (no certresolver label).
- Images pinned to specific tags — no `latest`. CWA: `ghcr.io/crocodilestick/calibre-web-automated:V3.1.4` (current stable release as of 2026-09-21, per https://github.com/crocodilestick/Calibre-Web-Automated/releases). `library-digest` base: `python:3.12.8-slim`.
- `PUID`/`PGID` already exist as top-level `.env` vars (`1000`/docker-group-gid) — reuse them, don't hardcode `1000` in the compose file (the brief's script does hardcode 1000 for `os.chown`; keep that but note it must match `.env`'s `PUID`/`PGID` in the doc).
- AdGuard already rewrites `*.${DOMAIN}` (wildcard, confirmed in `scripts/adguard/setup-adguard-dns.sh`) — no per-host DNS work needed.
- No secrets committed; nothing exposed publicly; no firewall changes.
- `.env.example` only gains vars the repo actually reads at runtime (`DIGEST_INTERVAL`), following the existing per-service comment-block style.
- GitHub Flow: feature branch (`feature/ebook-library`), squash merge — per `CLAUDE.md`.

---

### Task 1: `docker-compose.library.yml` + data dirs + `.gitignore`

**Files:**
- Create: `docker-compose.library.yml`
- Modify: `.gitignore` (add `data/cwa/`-style entries — but note `.gitignore` already has a blanket `data/` ignore, see step 1)
- Test: `docker compose -f docker-compose.library.yml config`

**Interfaces:**
- Consumes: external network `home-server-stack_homeserver` (already created by `docker-compose.yml`).
- Produces: two services, `cwa` (port 8083 internally, Traefik host `books.${DOMAIN}`) and `library-digest` (no exposed port), sharing the bind mount `./data/cwa/ingest` — later tasks (digest script, Makefile target, docs) reference these exact container/service names.

- [ ] **Step 1: Confirm `.gitignore` already covers the new data dirs**

  Read `.gitignore` — it has a blanket `data/` entry, so `data/cwa/` and `data/library-digest/` are already ignored. No edit needed. (The brief's task 6 assumed per-service entries; the repo's actual convention is a single blanket rule — follow the repo.)

- [ ] **Step 2: Write `docker-compose.library.yml`**

```yaml
# Ebook library: Calibre-Web-Automated at books.${DOMAIN} + a daily RSS-to-EPUB digest.
# Follows the conventions of docker-compose.photos.yml (external homeserver network,
# Traefik labels with the wildcard cert, admin middleware).
#
# One-time prep:
#   mkdir -p data/cwa/{config,ingest,library} data/library-digest
#   chown -R ${PUID}:${PGID} data/cwa data/library-digest

services:
  cwa:
    image: ghcr.io/crocodilestick/calibre-web-automated:V3.1.4
    container_name: cwa
    restart: unless-stopped
    networks:
      - homeserver
    environment:
      PUID: ${PUID:-1000}
      PGID: ${PGID:-1000}
      TZ: ${TIMEZONE:-UTC}
    volumes:
      - ./data/cwa/config:/config
      - ./data/cwa/ingest:/cwa-book-ingest    # drop EPUB/PDF here; CWA imports/converts and clears it
      - ./data/cwa/library:/calibre-library
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.books.rule=Host(`books.${DOMAIN}`)"
      - "traefik.http.routers.books.entrypoints=websecure"
      - "traefik.http.routers.books.tls=true"
      - "traefik.http.services.books.loadbalancer.server.port=8083"
      # Local/VPN only. The no-ratelimit variant is used because Kobo sync makes bursts
      # of requests (metadata, covers) that the 10 req/min admin limit would throttle.
      - "traefik.http.routers.books.middlewares=admin-secure-no-ratelimit"

  library-digest:
    image: python:3.12.8-slim
    container_name: library-digest
    restart: unless-stopped
    networks:
      - homeserver
    environment:
      TZ: ${TIMEZONE:-UTC}
      DIGEST_PUID: ${PUID:-1000}
      DIGEST_PGID: ${PGID:-1000}
    volumes:
      - ./scripts/library:/app:ro
      - ./config/library:/config:ro           # feeds.txt lives here
      - ./data/library-digest:/data           # seen.json (what's already been bundled)
      - ./data/cwa/ingest:/ingest
    # Runs at container start, then every DIGEST_INTERVAL seconds (drifts from start
    # time; fine for a daily digest, not a cron guarantee).
    command: >
      sh -c "pip install -q feedparser ebooklib &&
      while true; do python /app/digest.py; sleep ${DIGEST_INTERVAL:-86400}; done"

networks:
  homeserver:
    external: true
    name: home-server-stack_homeserver
```

  Note vs. the brief: `library-digest` didn't originally join the `homeserver` network, but it needs outbound access to fetch RSS feeds and Docker's default bridge is fine for that — added it anyway for consistency with every other service in the stack (harmless, and matches repo convention of every service declaring `networks: [homeserver]`). Also switched the hardcoded `PUID`/`PGID: 1000` to `${PUID:-1000}`/`${PGID:-1000}` env-var refs (`DIGEST_PUID`/`DIGEST_PGID` for the digest container, consumed by the script in Task 2), matching how `docker-compose.dashboard.yml` and `.env.example` already parameterize these.

- [ ] **Step 3: Validate config syntax**

  Run: `docker compose -f docker-compose.library.yml config --quiet`
  Expected: no output, exit code 0. (`DOMAIN`, `PUID`, `PGID`, `TIMEZONE` come from `.env` — if this is run standalone without `.env` sourced, expect warnings about unset vars; that's fine, `make validate` sources `.env` via the full `$(COMPOSE)`.)

- [ ] **Step 4: Commit**

```bash
git add docker-compose.library.yml
git commit -m "feat: add docker-compose.library.yml for CWA ebook library"
```

---

### Task 2: `scripts/library/digest.py` + `config/library/feeds.txt`

**Files:**
- Create: `scripts/library/digest.py`
- Create: `config/library/feeds.txt`
- Test: manual run inside a throwaway container (Step 3 below) — no existing Python test harness in this repo to extend, so this is a runtime smoke test, not a pytest suite.

**Interfaces:**
- Consumes: `/config/feeds.txt` (newline-separated feed URLs, `#`-prefixed comments/blank lines skipped), `/data/seen.json` (JSON array of entry ids/links already bundled), env vars `DIGEST_PUID`/`DIGEST_PGID` (from Task 1's compose file, default `1000`/`1000` if unset).
- Produces: `/ingest/reading-YYYY-MM-DD.epub` when there's new content; always rewrites `/data/seen.json`. Exit code 0 in both the "wrote a book" and "nothing new" cases.

- [ ] **Step 1: Write `config/library/feeds.txt`**

```
# One RSS URL per line. Any Substack's feed is https://<name>.substack.com/feed
# Replace these placeholders with the writers you actually want.
https://example.substack.com/feed
# https://another.substack.com/feed
```

  (Per the brief: leave placeholders, the owner supplies the real list — this file is checked in as a template others can edit locally.)

- [ ] **Step 2: Write `scripts/library/digest.py`**

```python
"""Bundle new posts from feeds.txt into one EPUB and drop it in the CWA ingest folder."""
import datetime
import json
import os
import pathlib

import feedparser
from ebooklib import epub

FEEDS = pathlib.Path("/config/feeds.txt")
STATE = pathlib.Path("/data/seen.json")
OUT = pathlib.Path("/ingest")
MAX_PER_FEED = 5  # cap per feed per run, so the first run isn't a huge backlog

# Matches the PUID/PGID the cwa container runs as (set via DIGEST_PUID/DIGEST_PGID
# in docker-compose.library.yml, defaulting to 1000/1000) so CWA's ingest watcher
# can read and delete the file after import.
OWNER_UID = int(os.environ.get("DIGEST_PUID", "1000"))
OWNER_GID = int(os.environ.get("DIGEST_PGID", "1000"))

seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
posts = []

urls = [
    line.strip()
    for line in FEEDS.read_text().splitlines()
    if line.strip() and not line.strip().startswith("#")
]

for url in urls:
    feed = feedparser.parse(url)
    source = feed.feed.get("title", url)
    new = [e for e in feed.entries if (e.get("id") or e.get("link")) not in seen]
    # Mark everything as seen, but only include the newest few
    for e in feed.entries:
        seen.add(e.get("id") or e.get("link"))
    for e in new[:MAX_PER_FEED]:
        body = e.content[0].value if e.get("content") else e.get("summary", "")
        posts.append((source, e.get("title", "Untitled"), e.get("link", ""), body))

if not posts:
    print("Nothing new.")
    STATE.write_text(json.dumps(sorted(seen)))
    raise SystemExit

today = datetime.date.today().isoformat()
book = epub.EpubBook()
book.set_identifier(f"digest-{today}")
book.set_title(f"Reading list {today}")
book.set_language("en")
book.add_author("Digest")

chapters = []
for i, (source, title, link, body) in enumerate(posts, 1):
    ch = epub.EpubHtml(title=title, file_name=f"post{i}.xhtml", lang="en")
    ch.content = f"<h1>{title}</h1><p><em>{source}</em></p>{body}"
    book.add_item(ch)
    chapters.append(ch)

book.toc = tuple(chapters)
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
book.spine = ["nav"] + chapters

path = OUT / f"reading-{today}.epub"
epub.write_epub(str(path), book)
os.chown(path, OWNER_UID, OWNER_GID)
STATE.write_text(json.dumps(sorted(seen)))
print(f"Wrote {path} with {len(posts)} posts.")
```

  Deviation from the brief: `os.chown` now reads `DIGEST_PUID`/`DIGEST_PGID` (defaulting to 1000/1000) instead of a hardcoded `1000, 1000`, so it stays correct if the owner's `.env` `PUID`/`PGID` differ from 1000 (matches how `docker-compose.dashboard.yml` parameterizes ownership). Known limits carried over unfixed (documented in Task 4's docs page, not silently dropped): remote images in post bodies won't render offline on the Kobo; paid-Substack posts only get the free RSS preview; no cross-feed de-duplication by title.

- [ ] **Step 3: Smoke-test the script manually (no `.env` / stack required)**

  This repo has no Python test runner to hook into, so verify with a disposable container against a real public feed:

  ```bash
  mkdir -p /tmp/library-smoke/config /tmp/library-smoke/data /tmp/library-smoke/ingest
  echo "https://example.substack.com/feed" > /tmp/library-smoke/config/feeds.txt
  docker run --rm \
    -v "$PWD/scripts/library:/app:ro" \
    -v /tmp/library-smoke/config:/config:ro \
    -v /tmp/library-smoke/data:/data \
    -v /tmp/library-smoke/ingest:/ingest \
    python:3.12.8-slim \
    sh -c "pip install -q feedparser ebooklib && python /app/digest.py"
  ls /tmp/library-smoke/ingest
  ```

  Expected: either `Wrote reading-<today>.epub with N posts.` and a file in `/tmp/library-smoke/ingest`, or `Nothing new.` if the placeholder feed doesn't resolve/has no entries — both are acceptable proof the script runs without a traceback. Swap in a real feed URL (e.g. a live Substack `/feed`) if the placeholder doesn't return entries, to confirm the EPUB actually gets written once.

  Re-run the same command a second time: expected `Nothing new.` (proves `seen.json` de-dupe works).

  Clean up: `rm -rf /tmp/library-smoke`

- [ ] **Step 4: Commit**

```bash
git add scripts/library/digest.py config/library/feeds.txt
git commit -m "feat: add RSS-to-EPUB digest script for ebook library"
```

---

### Task 3: Makefile integration

**Files:**
- Modify: `Makefile:5` (`.PHONY` line for `logs-*` targets), `Makefile:29` (`COMPOSE` variable), `Makefile:333-345` (logs-* target block), and add a new `library-digest-now` target near the other one-off/manual targets.

**Interfaces:**
- Consumes: `docker-compose.library.yml` from Task 1 (service names `cwa`, `library-digest`).
- Produces: `make logs-cwa`, `make logs-library-digest`, `make library-digest-now` targets; `library-digest` and `cwa` now start/stop/update/status with every other service via `$(COMPOSE)`.

- [ ] **Step 1: Add the compose file to `$(COMPOSE)`**

  In `Makefile`, change:
  ```makefile
  COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml
  ```
  to:
  ```makefile
  COMPOSE := docker compose -f docker-compose.yml -f docker-compose.network.yml -f docker-compose.monitoring.yml -f docker-compose.dashboard.yml -f docker-compose.photos.yml -f docker-compose.location.yml -f docker-compose.immich.yml -f docker-compose.library.yml
  ```

  Also update the header comment block (`# Services are organized into logical groups:`) to add a line:
  ```
  # - docker-compose.library.yml: Ebook library (cwa, library-digest)
  ```

- [ ] **Step 2: Add `.PHONY` entries and log targets**

  Change:
  ```makefile
  .PHONY: logs-n8n logs-homepage logs-owntracks logs-icloudpd logs-immich
  ```
  to:
  ```makefile
  .PHONY: logs-n8n logs-homepage logs-owntracks logs-icloudpd logs-immich logs-cwa logs-library-digest
  .PHONY: library-digest-now
  ```

  After the existing `logs-immich:` target (around line 345), add:
  ```makefile
  logs-cwa:
  	@$(COMPOSE) logs -f cwa

  logs-library-digest:
  	@$(COMPOSE) logs -f library-digest
  ```

- [ ] **Step 3: Add a `library-digest-now` target**

  Add near the other individual-service targets (after the new `logs-library-digest` target is a reasonable spot):
  ```makefile
  # Run the RSS-to-EPUB digest once, immediately, instead of waiting for the
  # container's internal sleep loop.
  library-digest-now:
  	@$(COMPOSE) exec library-digest python /app/digest.py
  ```

  Also add `- "  make library-digest-now       - Run the reading digest once, immediately"` to the `help` target's `Logs & Debugging` or a new line, matching the existing `@echo` style — insert it right after the `logs-owntracks` help line at Makefile:61.

- [ ] **Step 4: Verify**

  Run: `make validate`
  Expected: `✓ Docker Compose configuration is valid` (requires `.env` to exist locally; if not, `cp .env.example .env` first — this is a syntax check only, no services actually start on the Mac per `CLAUDE.md`).

  Run: `make help | grep -i "library\|logs-cwa"`
  Expected: the new lines appear.

- [ ] **Step 5: Commit**

```bash
git add Makefile
git commit -m "feat: wire docker-compose.library.yml into Makefile targets"
```

---

### Task 4: `.env.example`, Homepage dashboard tile, and `SERVICES.md`

**Files:**
- Modify: `.env.example` (append a new section)
- Modify: `config/homepage/services-template.yaml` (append a new tile)
- Modify: `SERVICES.md` (add entry under "Running")

**Interfaces:**
- Consumes: `books.${DOMAIN}` route from Task 1.
- Produces: `DIGEST_INTERVAL` documented as an optional env var; a Homepage tile linking to `https://books.${DOMAIN}`.

- [ ] **Step 1: Append to `.env.example`**

  After the Immich section at the end of the file, add:
  ```
  # =============================================================================
  # Ebook Library (Calibre-Web-Automated + daily reading digest)
  # =============================================================================
  # CWA serves the library and acts as a Kobo sync server at https://books.${DOMAIN}
  # (LAN/VPN only). See docs/ebook-library.md for first-run setup and Kobo pairing.
  # library-digest turns config/library/feeds.txt into one EPUB per day, dropped
  # into data/cwa/ingest/ for CWA to auto-import.

  # How often (seconds) library-digest checks feeds.txt for new posts. Optional —
  # defaults to 86400 (once a day) if unset.
  DIGEST_INTERVAL=86400
  ```

- [ ] **Step 2: Add a Homepage tile**

  Check `config/homepage/services-template.yaml` for the section that lists direct service links (not the widget-heavy "Today"/"Transport" groups) — likely a group named after running services (grep for `Immich:` or `n8n:` entries to find the right group first: `grep -n "Immich:\|n8n:" config/homepage/services-template.yaml`). Add a sibling entry following that group's existing format, e.g.:
  ```yaml
    - Ebook Library:
        icon: mdi-bookshelf
        href: https://books.{{HOMEPAGE_VAR_DOMAIN}}
        description: Calibre-Web-Automated + Kobo sync
  ```
  Match whatever templating variable the file already uses for other services' domains (grep first — some entries use a literal `books.${DOMAIN}` Traefik-style string vs. Homepage's own `{{HOMEPAGE_VAR_*}}` substitution; follow whatever `Immich`'s tile actually does, since it's the most recent precedent).

- [ ] **Step 3: Add to `SERVICES.md`**

  Under "## Running", following the existing per-service subsection format (see the Immich or icloudpd entries for the exact shape), add:
  ```markdown
  #### Ebook Library (Calibre-Web-Automated)
  - **Purpose:** Self-hosted EPUB/PDF library and Kobo sync server, fed by a daily
    RSS digest of curated reading
  - **Access:** https://books.${DOMAIN}
  - **Authentication:** IP-restricted (local network / VPN only) + CWA's own login
  - **Features:**
    - Kobo Sync API for wireless delivery to a Kobo Clara BW over home Wi-Fi
    - `library-digest` sidecar bundles new posts from `config/library/feeds.txt`
      into one EPUB/day and drops it into CWA's ingest folder
  ```

- [ ] **Step 4: Commit**

```bash
git add .env.example config/homepage/services-template.yaml SERVICES.md
git commit -m "docs: add ebook library to .env.example, Homepage, and SERVICES.md"
```

---

### Task 5: `docs/ebook-library.md` and `CLAUDE.md`/`README.md` cross-references

**Files:**
- Create: `docs/ebook-library.md`
- Modify: `README.md` (add to whatever list references `docs/*.md` — check how `docs/immich-photo-viewer.md` is linked there first)
- `CLAUDE.md`: no changes needed — it doesn't enumerate individual services (verify by re-reading `CLAUDE.md`'s Architecture section; it references compose *files*, which Task 3 already documented in the Makefile's own header comment, not in `CLAUDE.md` itself). Skip editing `CLAUDE.md` unless that check finds otherwise.

**Interfaces:**
- Consumes: manual setup steps from the brief's section 6, acceptance checks from section 7.
- Produces: `docs/ebook-library.md`, the doc other tasks (and the owner) reference for first-run setup.

- [ ] **Step 1: Check how `README.md` references per-service docs**

  Run: `grep -n "docs/" README.md`
  Follow whatever pattern it uses for `docs/immich-photo-viewer.md` / `docs/icloud-photos-backup.md` (a table row, a bullet list, etc.) and add an equivalent row/bullet for `docs/ebook-library.md` in Step 4.

- [ ] **Step 2: Write `docs/ebook-library.md`**

```markdown
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
```

- [ ] **Step 3: Cross-link from README.md**

  Add a row/bullet for `docs/ebook-library.md` matching whatever format Step 1 found — e.g. if `README.md` has a docs table, add:
  ```markdown
  | [Ebook Library](docs/ebook-library.md) | Calibre-Web-Automated + Kobo sync setup |
  ```

- [ ] **Step 4: Commit**

```bash
git add docs/ebook-library.md README.md
git commit -m "docs: add ebook library setup and troubleshooting guide"
```

---

### Task 6: Full validation and PR

**Files:** none (verification + PR only)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: an open PR per the repo's GitHub Flow.

- [ ] **Step 1: Create the feature branch (if not already on one)**

```bash
git checkout main && git pull
git checkout -b feature/ebook-library
```

  (If Tasks 1-5 were already committed on `main` directly, `git branch feature/ebook-library` from the current commit and reset `main` back — the repo's workflow requires a feature branch before PR, per `CLAUDE.md`.)

- [ ] **Step 2: Run the full validation suite**

```bash
cp -n .env.example .env  # if .env doesn't already exist locally
make validate
docker compose -f docker-compose.library.yml config --quiet
```

  Expected: both pass with no errors.

- [ ] **Step 3: Document what could not be verified**

  This work happens on the dev Mac per `CLAUDE.md` ("this stack runs on a dedicated home server, not the dev Mac") — actually bringing up `cwa`/`library-digest`, testing Kobo pairing, and confirming `books.${DOMAIN}` resolves with a valid cert all require the real server and a physical Kobo. Note this explicitly in the PR body (see Step 5) rather than claiming it was tested.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feature/ebook-library
gh pr create --title "feat: add self-hosted ebook library (CWA + Kobo sync + RSS digest)" --body "$(cat <<'EOF'
## Summary
- Adds docker-compose.library.yml: Calibre-Web-Automated (books.${DOMAIN}, LAN/VPN only) + a library-digest sidecar
- library-digest bundles config/library/feeds.txt into one EPUB/day via scripts/library/digest.py, dropped into CWA's ingest folder
- Wires the new compose file into Makefile (COMPOSE var, logs-cwa, logs-library-digest, library-digest-now)
- Adds .env.example (DIGEST_INTERVAL), a Homepage tile, a SERVICES.md entry, and docs/ebook-library.md (setup, Kobo pairing, troubleshooting)

## Not verified (requires the real server + a physical Kobo)
- Bringing the containers up and confirming books.${DOMAIN} resolves with a valid cert
- Actual Kobo pairing and wireless sync
- CWA's ingest auto-import timing

## Known limitations (documented in docs/ebook-library.md)
- No image embedding in digest EPUBs; paid Substack posts get preview-only RSS; no cross-feed de-dup

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Report back**

  Summarize the PR URL and the "not verified" list to the user — do not claim the stack was tested end-to-end.
