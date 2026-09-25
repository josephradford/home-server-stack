# Kitchen Kiosk — Project Brief

## What this is
A self-hosted, always-on kitchen display. Default state is an ambient photo slideshow (screensaver-style) with a light info overlay. Touching the screen reveals panels for radio, calendar detail, and recipes. No social media, no video streaming — everything glanceable or purpose-built.

## Hardware / environment
- **Client device:** Existing 11" iPad (A16, USB-C). Used for software development for now — a final stand/dock is a separate, later decision and doesn't block the build.
- **Audio:** device's own speaker only.
- **Server:** existing home server, Docker on Ubuntu, Traefik as reverse proxy already running. New service(s) should slot in as another Traefik-routed container.
- **Network scope:** local network only. No need to function if the server is down — no offline/cached mode required.

## Recommended architecture
1. **One small backend service** (Node/Express or Python/FastAPI) that aggregates all data sources server-side and exposes a single local API to the frontend. Avoids CORS issues from calling Google/Apple/Immich directly from the client, and gives one place to add live-update push (websocket/SSE) later.
   - Aggregates multiple Google + Apple (iCloud) calendar iCal feeds into one merged event list.
   - Proxies Immich photo listing + metadata (date taken, place name).
   - Serves the recipe markdown folder as structured JSON (parse frontmatter/sections).
   - Normalizes BOM weather data into one simple shape.
2. **A frontend kiosk page** (single-page app or plain JS) that is the only thing the device's browser ever loads, running full-screen in Safari added to the Home Screen (Web App mode) with iOS Guided Access enabled to lock navigation — Fully Kiosk Browser and similar apps are Android-only, so the iOS equivalent is Guided Access (Settings > Accessibility) triple-clicking the side button to lock/unlock, plus enabling "Auto-Lock: Never" so the screen doesn't sleep on its own outside the scheduled sleep window below.
3. **Build order suggestion:**
   - First: prove the kiosk shell survives an iPad reboot and a server reboot unattended, running just a placeholder page — before building any feature.
   - Second: build the backend aggregation service.
   - Third: build the screensaver/idle view fully (photos + overlay), since it's the default state 99% of the time.
   - Fourth: add touch panels one at a time (radio is simplest — no auth, just stream URLs).
   - Fifth: add the scheduled sleep/downtime behavior once the core views work.

## Idle state (screensaver mode)
- Full-screen photo slideshow sourced from Immich (via Immich Kiosk or a custom feed from the Immich API).
- Light, corner-anchored overlay (not a dashboard layered on the photo):
  - Time / date
  - Weather — current + short forecast, BOM-sourced (Sydney)
  - Next 1–2 calendar events (title + time only)
  - Photo metadata (as Immich Kiosk shows) — date taken, place name if available
- Returns to idle automatically after a period of no touch — **but only while the screensaver itself is showing.** If a non-photo panel is open (recipe, calendar detail, radio), the idle timer does not run, so an open recipe won't get interrupted by someone standing at the bench reading it. The panel returns to idle only once closed, or after its own separate, longer inactivity timeout.

## Touch state (interactive panels)
Triggered by any touch on the idle screen:
- **Radio** — preset list: ABC Cricket, ABC Classic, Double J, ABC Jazz. Tap to start/stop playback via `<audio>` and each station's stream URL — no auth needed.
- **Calendar** — tap the shown event (or a calendar icon) for a full day/week view and event details. Read-only (iCal feeds), no event creation from the kiosk.
- **Recipes** — browse a short, mostly-static list of favourites; tap to view one in full. Source: a folder of plain markdown files (title/ingredients/steps per file), hand-edited directly on the server — no in-place editing UI on the kiosk.

## Sleep / downtime state
- The display sleeps (screen off, slideshow paused) during scheduled downtime — primarily overnight, and optionally whenever nobody is home.
- Presence for "nobody home" via either/both:
  - **Wi-Fi presence** — checking which known devices (phones) are currently associated with the home network (router API or ARP scan). Simpler to build first, no extra hardware.
  - **Motion/PIR sensor** — signals recent kitchen activity; more setup (needs a physical sensor talking to the backend), deferred if Wi-Fi presence alone is enough to start.
- A touch on the sleeping screen always wakes it instantly — sleep never blocks manual wake.
- Waking returns to the idle screensaver, not whatever panel was open before sleeping.

## Non-functional requirements
- **Live-updating:** calendar, weather, and now-playing state should reflect changes without a manual refresh (polling is fine to start; websocket/SSE if polling proves too slow).
- **Resilience:** must survive reboots of both the server and the iPad unattended — the kiosk web app relaunches into Guided Access on device restart and auto-reconnects to the backend, no manual restart ever required.
- **Touch-first:** idle overlay is view-only; touch unlocks navigation.

## Explicitly out of scope
- Social media of any kind.
- Video streaming (Netflix, YouTube, etc.).
- External/internet-facing access — local network only.
- Spotify — considered and dropped. It would need its own OAuth/login and playback setup (Premium account, Web Playback SDK or Connect casting) rather than a simple stream URL like the radio presets, adding account-management complexity not worth it for this project.
- Camera-based presence detection — considered as a way to avoid interrupting someone reading a recipe, but rejected: an always-on camera pointed at the kitchen is a meaningful privacy/complexity cost, and the idle-timer-pause behavior above already solves the actual problem without a sensor.

## Deferred to v2
- **OwnTracks location widget** — only useful when away from home (needs a VPN connection back to the house to report). Best as a touch panel ("check where's everyone") rather than a default overlay item.
- **Real presence detection** — if wanted later, a PIR motion sensor (binary signal only, no camera/video) is the lower-cost path versus a camera.
