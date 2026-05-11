# GTFS-RT Light Rail Transport Widget — Research Spec

**Date:** 2026-05-12
**Author:** Joe Radford + Claude
**Status:** Research complete — not yet implemented

---

## 1. Problem

The homepage transport widget shows Parramatta Light Rail (L4) departure times that are consistently ~2 minutes behind TripView. Bus departures are accurate.

### Root cause

The homepage-api uses the TFNSW `departure_mon` endpoint, a high-level JSON abstraction over the raw realtime feeds. For light rail specifically:

- Light rail GTFS static timetables are updated **manually** (buses are automated), so when service patterns change, the realtime system can fail to match running vehicles to trips.
- When matching fails, `departure_mon` silently falls back to scheduled times instead of realtime — making departures appear "on time" when there's actually no live tracking.
- The `departure_mon` endpoint adds processing overhead on top of the raw GTFS-RT feed, introducing latency.

TripView likely consumes the raw GTFS-RT protobuf feed directly, which updates every 10-15 seconds from the operational system with no abstraction layer.

### Supporting evidence

- [TFNSW forum: Realtime Feed Down — CBD and South East Light Rail](https://opendataforum.transport.nsw.gov.au/t/realtime-feed-down-cbd-and-south-east-light-rail-timetable-update/8584) (April 2026) — documents exactly this timetable matching failure
- [TFNSW forum: Public Transport — Light Rail Realtime data](https://opendataforum.transport.nsw.gov.au/t/public-transport-light-rail-realtime-data/3525)
- TFNSW troubleshooting docs: "Light Rail GTFS data feeds are updated ad-hoc as it is a manual process"

## 2. Proposed fix

Replace the `departure_mon` API call with direct GTFS-RT protobuf feed consumption for light rail stops only. Keep `departure_mon` for buses (where it works well).

## 3. GTFS-RT API details

### Endpoints (Parramatta Light Rail)

| Feed | URL |
|------|-----|
| Realtime Trip Updates | `https://api.transport.nsw.gov.au/v1/gtfs/realtime/lightrail/parramatta` |
| Vehicle Positions | `https://api.transport.nsw.gov.au/v1/gtfs/vehiclepos/lightrail/parramatta` |
| Static Schedule (GTFS ZIP) | `https://api.transport.nsw.gov.au/v1/gtfs/schedule/lightrail/parramatta` |

Authentication: same `apikey` header already used by `departure_mon`.

### Protobuf schema

Standard GTFS-RT proto2 (`gtfs-realtime.proto`). TFNSW has extensions (field 1007 on `VehicleDescriptor`) but these only apply to vehicle positions — trip updates use the standard schema.

Use `?debug=true` query parameter during development to get human-readable text-format output instead of binary.

### Python dependencies

```
gtfs-realtime-bindings==2.0.0
protobuf>=4.0
```

### Stop ID mapping

**Critical:** GTFS-RT uses different stop IDs than the `departure_mon` API.

- Current `.env` IDs (e.g. `2151158`, `10101713`) are EFA/Trip Planner IDs
- GTFS-RT uses Transit Stop Numbers from `stops.txt` in the static GTFS bundle

To map: download the static GTFS ZIP, extract `stops.txt`, match by stop name or coordinates. Only 2 tram stops are configured, so a manual mapping table is practical.

### Static GTFS data

Needed to resolve `trip_id` → route/destination and `stop_id` → stop name.

Key files in the ZIP: `routes.txt`, `trips.txt`, `stops.txt`, `stop_times.txt`, `calendar.txt`.

The static feed updates ad-hoc (not on a schedule). Caching with a weekly refresh is sufficient.

## 4. Implementation sketch

```python
from google.transit import gtfs_realtime_pb2

def get_gtfsrt_departures(stop_id, gtfs_stop_id):
    """Fetch departures from GTFS-RT feed for a light rail stop."""
    url = 'https://api.transport.nsw.gov.au/v1/gtfs/realtime/lightrail/parramatta'
    headers = {
        'Authorization': f'apikey {TRANSPORT_NSW_API_KEY}',
        'Accept': 'application/x-google-protobuf'
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    results = []
    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip = entity.trip_update
            for stu in trip.stop_time_update:
                if stu.stop_id == gtfs_stop_id:
                    results.append({
                        'trip_id': trip.trip.trip_id,
                        'route_id': trip.trip.route_id,
                        'arrival': stu.arrival.time if stu.HasField('arrival') else None,
                        'departure': stu.departure.time if stu.HasField('departure') else None,
                        'delay_seconds': stu.departure.delay if stu.HasField('departure') else 0,
                    })
    return results
```

### Additional work needed

1. **Stop ID discovery** — download GTFS static bundle, find GTFS stop IDs for Ngara and Parramatta Square
2. **Route/destination resolution** — parse `trips.txt` + `routes.txt` to map `trip_id` → destination name and line number
3. **New env vars** — add `TRANSPORT_STOP_X_GTFS_ID` or build a lookup table in the API
4. **Fallback** — if GTFS-RT returns no trip updates for a stop (feed is down or outside operating hours), fall back to `departure_mon`
5. **Polling interval** — GTFS-RT feed updates every 10-15 seconds; consider reducing `refreshInterval` from 60s to 30s for tram widgets
6. **Static GTFS caching** — download and cache the ZIP on startup, refresh weekly

### Rate limits (Bronze plan)

- 60,000 requests/day
- 5 requests/second throttle
- Shared across all endpoints on the same API key

At 30s refresh intervals for 2 tram stops (single feed covers both), that's ~2,880 requests/day — well within limits.

## 5. Gotchas

- L4 is the Parramatta line (Westmead & Carlingford). L2/L3 are CBD & South East.
- GTFS-RT feed omits trips with no realtime tracking — absence means "no data", not "on time". Must fall back to static timetable.
- L4 operates ~5am to ~1am. Feed will be empty outside these hours.
- The generic `/lightrail/` endpoint includes all light rail networks. Use `/lightrail/parramatta` to avoid parsing irrelevant data.
- New GHCR image build required after adding `gtfs-realtime-bindings` to `requirements.txt`.
