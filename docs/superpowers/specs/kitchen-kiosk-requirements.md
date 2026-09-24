# Kitchen Kiosk — Requirements

## Overview
A self-hosted, wall/counter-mounted touchscreen for the kitchen. Default state is an ambient photo slideshow (screensaver-style) with a light info overlay. Touching the screen reveals interactive panels for radio, calendar, and recipes. No social media, no video streaming, no infinite-scroll content — everything glanceable or purpose-built.

## Core Behavior

### Idle state (screensaver mode)
- Full-screen photo slideshow, sourced from Immich (via Immich Kiosk or a custom feed from the Immich API).
- Light overlay on top of photos, always visible:
  - Time / date
  - Weather (current + short forecast, BOM-sourced)
  - Next 1–2 calendar events (title + time only)
  - Photo metadata (as Immich Kiosk shows) — e.g. date taken, location/place name if available
- Overlay should be unobtrusive — small, corner-anchored text/icons, not a dashboard layered on the photo.
- Returns to this state automatically after a period of no touch input — but only while the current view is the screensaver/overlay itself. If a non-photo panel (recipe, calendar detail, radio) is open, the idle timer does not run, so an open recipe won't be interrupted by someone standing at the bench reading it. The panel only returns to the screensaver after it is closed or after its own separate, longer inactivity timeout.

### Touch state (interactive mode)
Triggered by any touch on the idle screen. Reveals additional navigation/panels:
- **Radio** — pick from a short list of preset stations (ABC + others as wanted); tap to start/stop playback.
- **Calendar** — tap the shown event (or a calendar icon) to see full day/week view and event details.
- **Recipes** — browse a short, mostly-static list of favourites, tap to view a recipe in full.

### Sleep / downtime state
- The display goes to sleep (screen off, slideshow paused) during scheduled downtime windows — primarily overnight, and optionally whenever nobody is home.
- Presence for "nobody home" can be detected via:
  - **Wi-Fi presence** — checking which known devices (phones) are currently associated with the home network (e.g. via router API, ARP scan, or a presence-detection tool).
  - **Motion/presence sensor** — a PIR or similar sensor signalling recent activity in the kitchen (see the existing presence-detection note in Future/v2 below — a PIR is the lower-cost, non-camera option this would also serve).
- A touch on the sleeping screen always wakes it immediately, regardless of the schedule or presence state — sleep never blocks manual wake.
- Waking from a scheduled sleep returns straight to the idle screensaver state (not any panel that may have been open before sleeping).

| Requirement | Detail |
|---|---|
| **Hosting** | Home server (Docker/Ubuntu), local network only — no external exposure needed |
| **Client device** | Existing 11" iPad (A16, USB-C), used for software development for now — final stand/dock hardware decision deferred until the software works |
| **Audio** | Tablet's own speaker only |
| **Update model** | Live-updating — calendar, weather, and now-playing state should reflect changes without a manual refresh (websocket or polling) |
| **Interaction** | Touch-first; idle overlay is view-only, touch unlocks navigation |
| **Resilience** | Must survive reboots of both the server and the display device unattended — kiosk browser auto-launches and reconnects, no manual restart needed |
| **Network scope** | Local network only; no requirement to function if the home server is down (no offline/cached mode needed) |
| **Sleep schedule** | Configurable overnight sleep window, plus optional presence-based sleep (Wi-Fi device detection and/or a motion/PIR sensor) when the apartment is empty; touch always wakes instantly |

## Data Sources
- **Photos** — Immich (existing library / albums)
- **Calendar** — Multiple Google and Apple (iCloud) calendar accounts, merged via their iCal feed URLs
- **Weather** — BOM (Bureau of Meteorology) for Sydney accuracy
- **Radio** — ABC Cricket, ABC Classic, Double J, ABC Jazz (preset list, no others needed)
- **Recipes** — Folder of plain markdown files (title/ingredients/steps per file), hand-edited directly, no in-place editing UI on the kiosk

## Future / v2 Considerations
- Location widget via OwnTracks — only meaningful when away from home, since OwnTracks won't report a live location without a VPN connection back to the home network. Best suited as a touch panel ("check where's everyone") rather than a default overlay item. Deferred to v2.
- Presence detection — considered camera-based detection (front camera + motion/face model) to keep a panel open while someone's nearby, but this means an always-on camera pointed at the kitchen, which is a meaningful privacy/complexity cost for limited benefit — especially since the idle-timer-pause approach above already solves the main annoyance (interrupted recipe view) without any sensor. If real presence detection is wanted later, a PIR motion sensor (no camera/video, just a binary signal) is the lower-cost path — deferred to v2.

## Explicitly Out of Scope
- Social media of any kind
- Video streaming (Netflix, YouTube, etc.)
- External/internet-facing access — local network only
- Spotify — considered and dropped; it would require its own OAuth/login and playback setup (Premium account, Web Playback SDK or Connect casting) rather than a simple stream URL like the ABC/Double J presets, adding account-management complexity the project doesn't need for v1
