# Kitchen Kiosk — Design Spec

## Overview

A self-hosted, wall/counter-mounted touchscreen kiosk for the kitchen, running on an
existing 11" iPad. Default state is an ambient full-screen photo slideshow (sourced
from Immich) with a light, corner-anchored info overlay: time/date, weather, next
calendar events, and photo metadata. Touching the screen reveals panels for radio,
calendar detail, and recipes. The display sleeps on a schedule and/or when nobody's
home, and always wakes instantly on touch.

Full requirements and rationale live in the source docs the user provided:
`kitchen-kiosk-requirements.md` and `kitchen-kiosk-brief.md`. This spec translates
those into the concrete shape for this repo.

Out of scope for v1: social media, video streaming, external/internet-facing access,
Spotify, camera-based presence detection. Deferred to v2: OwnTracks location panel,
PIR-sensor-based presence detection.

## Architecture

Two new services, added to this repo alongside the existing stack:

```
apps/kitchen-kiosk/
  backend/     # aggregation API
  frontend/    # kiosk single-page app
docker-compose.kiosk.yml
```

### `kiosk-api` (backend)

One small service that aggregates every data source server-side and exposes a single
local REST API to the frontend — avoids CORS issues calling Google/Apple/Immich
directly from the client, and gives one place to add push updates later. Stack:
Python/FastAPI, matching `homepage-api`'s existing stack in this repo.

Responsibilities:
- **Weather** — calls the existing `homepage-api` service's `GET /api/bom/weather`
  endpoint over the internal `homeserver` Docker network. No new BOM integration;
  reuses the `weather-au`-backed endpoint already serving the dashboard.
- **Calendar** — fetches and merges multiple Google + iCloud (Apple) iCal feed URLs
  into one normalized event list; polled and cached briefly server-side. Read-only —
  no event creation from the kiosk.
- **Photos** — queries the Immich API directly (not Immich Kiosk) for photo
  selection from configured album(s), returning image URLs plus metadata (date
  taken, place name where available). Custom feed gives full control over the
  overlay layout and lets photo metadata sit in the same response shape as
  calendar/weather for a single merged idle-state payload.
- **Recipes** — parses a mounted folder of markdown files (title/ingredients/steps
  per file) into structured JSON. Hand-edited directly on the server; no in-place
  editing UI.
- **Radio** — serves the static preset list (ABC Cricket, ABC Classic, Double J, ABC
  Jazz) with stream URLs; no auth, no proxying of the stream itself.

All endpoints are polled by the frontend (websocket/SSE deferred unless polling
proves too slow, per the brief).

### `kiosk-web` (frontend)

A single-page app — the only thing the iPad's browser ever loads — served
full-screen via iOS Safari "Add to Home Screen" (Web App mode) with iOS Guided
Access locking navigation, and "Auto-Lock: Never" so the OS doesn't sleep the
screen outside the app's own scheduled sleep window.

Views:
- **Idle/screensaver** — full-screen photo slideshow + overlay (time/date, weather,
  next 1–2 events, photo metadata). View-only; any touch transitions to touch state.
- **Radio panel** — preset list, tap to start/stop via `<audio>` + stream URL.
- **Calendar panel** — full upcoming event list (flat, sorted chronologically); day/week
  grouping deferred to v2.
- **Recipe panel** — browse list, tap to view one recipe in full.
- **Sleep state** — screen off / slideshow paused; any touch wakes instantly back to
  idle, regardless of schedule or presence state.

Idle-timeout behavior: the return-to-screensaver timer only runs while the idle
view itself is showing. Opening any panel suspends that timer, so an open recipe
is never interrupted; the panel returns to idle only when closed or after its own
separate, longer inactivity timeout.

### Networking

Traefik-routed as `kiosk.${DOMAIN}` and `kiosk-api.${DOMAIN}`, on the existing
`homeserver` Docker network, local-network-only (consistent with every other service
in this stack — no public exposure). Both routers carry the `admin-secure-no-ratelimit`
middleware (RFC1918 IP whitelist + security headers, same pattern as Immich) since
kiosk-api serves unauthenticated personal data (calendar events, photos) to the LAN;
the no-ratelimit variant is used because the frontend polls it continuously
(every 30-60s), which would trip the standard `admin-secure` rate limit.

### Sleep / presence (v1 scope)

- Configurable overnight sleep window (time-based), enforced by the frontend against
  server time or a scheduled flag from the backend.
- Optional Wi-Fi presence detection — built first, since it needs no extra hardware:
  backend checks which known devices (phones) are currently associated with the home
  network (router API or ARP scan) to decide "nobody home."
- PIR motion sensor support is deferred to v2 per the brief (more setup, extra
  hardware) unless Wi-Fi presence alone proves insufficient.
- Touch always wakes immediately; waking always returns to idle, never to whatever
  panel was open before sleep.

## Build Order

Per the brief's explicit sequencing — each stage should be independently verifiable
before moving to the next:

1. **Kiosk shell survives reboots** — placeholder page only, proves the iPad
   auto-launches into the kiosk web app and reconnects to the backend after both an
   iPad reboot and a server reboot, unattended.
2. **Backend aggregation service** — weather (via `homepage-api`), calendar, Immich
   photos, recipes, radio presets, all behind one API.
3. **Screensaver/idle view** — full slideshow + overlay, since it's the default
   state ~99% of the time.
4. **Touch panels, one at a time** — radio first (simplest, no auth), then calendar,
   then recipes.
5. **Scheduled sleep/downtime** — overnight window first, then optional Wi-Fi
   presence detection.

## Data Sources / Config (settle at implementation time, not design-blocking)

- Immich album(s)/query used for photo selection, and Immich API credentials.
- Recipe markdown folder path and its bind mount into the backend container.
- Exact stream URLs for the four radio presets.
- Google/iCloud calendar iCal feed URLs (per-account, added to `.env`).
- Wi-Fi presence detection method (router API vs ARP scan) — decide once the
  router's capabilities are checked.

## Testing

- `make validate` for compose syntax.
- Backend: unit tests per data-source module (calendar merge/normalize, recipe
  parsing, weather passthrough, Immich photo selection), following the pattern in
  `homepage-api/tests/`.
- Manual: `make test-domain-access` for the new `kiosk.${DOMAIN}` route; on-device
  verification for reboot resilience, Guided Access lock, and sleep/wake behavior
  (these aren't practically unit-testable).
