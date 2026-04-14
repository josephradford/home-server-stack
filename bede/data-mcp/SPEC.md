# Bede Data MCP — Design Spec

## Problem

Bede currently queries data sources (OwnTracks, InfluxDB) by making raw HTTP calls
with UTC timestamps and doing timezone math in its head. This is:

- **Token-expensive** — raw API responses contain dozens of unprocessed data points,
  requiring Bede to geocode, convert, and summarise in the same context window
- **Error-prone** — LLM timezone arithmetic is unreliable, especially across DST
  boundaries and day boundaries (a Sydney day spans two UTC dates)
- **Repetitive** — every query re-derives the same UTC offset logic
- **Incomplete** — a rich set of Mac/iPhone data is already pre-collected in the
  vault but Bede has no clean way to access it

## Data sources

There are two distinct categories of data source, which affect implementation:

### Vault-based (file reads)

A launchd job on Joe's Mac (`daily-raw-collect.sh` from the dotfiles repo) runs at
1:30am each night and commits the previous day's data to the Obsidian vault at:

```
/vault/data/daily-raw/YYYY-MM-DD/
```

The directory name (`YYYY-MM-DD`) is the **local date partition key** — a label, not
a timestamp. File contents use UTC ISO8601 for all per-event timestamps, so the MCP
has one consistent timezone strategy across all data sources.

Files with no per-event timestamps (aggregated durations) are unaffected. Human-readable
summary files (`vault-changes.txt`, `claude-sessions.md`) retain local time since they
are primarily for human consumption.

| File | Timestamps | Format |
|---|---|---|
| `screentime.csv` | None (aggregated seconds) | No change needed |
| `iphone-screentime.csv` | None (aggregated seconds) | No change needed |
| `safari-pages.csv` | `visited_at` per row | UTC ISO8601 |
| `youtube.csv` | `visited_at` per row | UTC ISO8601 |
| `podcasts.csv` | `played_at` per row | UTC ISO8601 |
| `vault-changes.txt` | Git log timestamps | Local time (human-readable) |
| `claude-sessions.md` | Session times | Local time (human-readable) |

**Dotfiles change required:** `daily-raw-collect.sh` currently outputs timestamps via
`datetime(..., 'localtime')` in SQLite. This needs to change to `datetime(..., 'utc')`
(or drop the modifier, since SQLite CoreData timestamps are already UTC-based) for
`safari-pages.csv`, `youtube.csv`, and `podcasts.csv`. The podcast `played_at`
and Safari `visited_at` columns should become UTC ISO8601 strings.

**DST note:** This change is particularly important around Australia's DST transition
(early April — exactly when OwnTracks data started). Local time is ambiguous at the
"fall back" hour; UTC is not.

### Live API

Two data sources require real-time queries:

| Source | URL | Data |
|---|---|---|
| OwnTracks Recorder | `http://owntracks-recorder:8083` | GPS location history |
| InfluxDB (HAE) | `http://hae-influxdb:8086` | Apple Health metrics + workouts |

Both return UTC timestamps. The MCP handles all timezone conversion internally.

---

## Solution

A purpose-built MCP server (`data-mcp`) that exposes clean, timezone-aware,
pre-summarised tools. Bede makes one tool call and gets a human-readable result.
All UTC conversion, file parsing, clustering, and geocoding happens in Python.

## Architecture

```
bede/data-mcp/
├── Dockerfile
├── requirements.txt
├── server.py              # FastMCP server entrypoint
└── sources/
    ├── vault.py           # Reads /vault/data/daily-raw/YYYY-MM-DD/ files
    ├── location.py        # OwnTracks Recorder client
    └── health.py          # InfluxDB / HAE client
```

Deployed as a Docker sidecar container, registered in `bede/.mcp.json` alongside
`workspace-mcp`:

```json
{
  "mcpServers": {
    "google-workspace": { "type": "http", "url": "http://workspace-mcp:8000/mcp" },
    "personal-data":    { "type": "http", "url": "http://data-mcp:8000/mcp" }
  }
}
```

### Framework

Use [FastMCP](https://github.com/jlowin/fastmcp) (Python) with `streamable-http`
transport — same pattern as `workspace-mcp`.

### Timezone handling

All tools accept an optional `timezone` parameter (default: `Australia/Sydney`).

All data sources use UTC timestamps. The MCP applies one consistent strategy:

1. Convert the requested local date to a UTC range using `zoneinfo`
2. Query or filter data using that UTC range
3. Convert all timestamps to the requested local timezone before returning

Bede never sees UTC. The `YYYY-MM-DD` directory name in the vault is a local date
partition key used only for file lookup — not treated as a timestamp.

---

## Tools

### Vault-based tools

#### `get_screen_time`
Returns app and web domain usage for a given local date.

**Parameters:**
- `date` — local date string (`YYYY-MM-DD`) or `"today"` / `"yesterday"`
- `device` — `"mac"` (default), `"iphone"`, or `"both"`
- `top_n` — return only the top N entries by duration (default: 20)

**Returns:**
```json
{
  "date": "2026-04-13",
  "device": "both",
  "apps": [
    {"name": "com.apple.Safari", "seconds": 3420, "device": "mac"},
    {"name": "com.reddit.Reddit", "seconds": 1800, "device": "iphone"}
  ],
  "web_domains": [
    {"domain": "github.com", "seconds": 2100}
  ]
}
```

#### `get_safari_history`
Returns Safari page visits for a given local date.

**Parameters:**
- `date` — local date string or natural string
- `device` — `"mac"`, `"iphone"`, or `"both"` (default)
- `domain_filter` — optional domain substring to filter by (e.g. `"youtube.com"`)
- `top_n` — limit results (default: 50)

**Returns:** Array of `{visited_at, domain, title, url, device}`.

#### `get_youtube_history`
Convenience wrapper around `get_safari_history` pre-filtered to YouTube visits.

**Parameters:**
- `date` — local date string or natural string

**Returns:** Array of `{visited_at, title, url, device}`.

#### `get_podcasts`
Returns podcast episodes played on a given local date.

**Parameters:**
- `date` — local date string or natural string

**Returns:** Array of `{episode, podcast, duration_minutes, played_at}`.

#### `get_vault_changes`
Returns a summary of Obsidian vault commits for a given local date.

**Parameters:**
- `date` — local date string or natural string

**Returns:**
```json
{
  "date": "2026-04-13",
  "commits": [
    {
      "hash": "abc1234",
      "time": "22:15",
      "message": "add meeting notes",
      "files": ["Projects/work/2026-04-13.md"]
    }
  ]
}
```

#### `get_claude_sessions`
Returns AI-generated summaries of Claude Code sessions for a given local date.
The summaries are pre-generated by `claude-sessions.py` at collection time —
no extra LLM call needed.

**Parameters:**
- `date` — local date string or natural string

**Returns:** Markdown string (the pre-generated `claude-sessions.md` content).

---

### Live API tools

#### `get_location_summary`
Returns a summarised list of stops for a given local date.

**Parameters:**
- `date` — local date string or natural string
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:**
```json
{
  "date": "2026-04-14",
  "timezone": "Australia/Sydney",
  "stops": [
    {
      "place": "North Parramatta",
      "address": "O'Connell Street, North Parramatta NSW 2151",
      "arrived": "08:00",
      "departed": "09:05",
      "activity": "stationary"
    },
    {
      "place": "Parramatta Aquatic Centre",
      "address": "Park Parade, Parramatta NSW 2150",
      "arrived": "09:13",
      "departed": "09:35",
      "activity": "walking"
    }
  ]
}
```

**Implementation notes:**
- Query UTC range = local date minus 1 day to local date plus 1 day, then filter
  by local timestamp after conversion
- Cluster raw GPS points into stops by proximity (points within 200m within a
  5-minute window = one stop)
- Reverse geocode once per stop cluster centroid via Nominatim (not once per point)
- Extract `place` from Nominatim `name` field if present, else suburb from `address`
- Add `User-Agent` header for Nominatim; cache geocoding results in memory

#### `get_location_raw`
Returns raw GPS points for a local date range without summarisation.

**Parameters:**
- `from_date`, `to_date` — local date strings
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:** Array of `{time, lat, lon, activity}` with local timestamps.

#### `get_sleep`
Returns sleep summary for a given local date (the night ending on that date).

**Parameters:**
- `date` — local date string or `"last_night"`
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:**
```json
{
  "date": "2026-04-14",
  "bedtime": "22:45",
  "wake_time": "06:08",
  "duration_hours": 7.4
}
```

#### `get_activity`
Returns daily activity summary.

**Parameters:**
- `date` — local date string or natural string
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:**
```json
{
  "date": "2026-04-14",
  "steps": 8423,
  "active_energy_kcal": 512,
  "exercise_minutes": 38,
  "move_minutes": 45,
  "stand_hours": 10
}
```

#### `get_workouts`
Returns workouts for a given local date.

**Parameters:**
- `date` — local date string or natural string
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:** Array of `{type, start_time, duration_minutes, energy_kcal}`.

#### `get_heart_rate`
Returns resting heart rate and HRV for a given local date.

**Parameters:**
- `date` — local date string or natural string
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:**
```json
{
  "date": "2026-04-14",
  "resting_heart_rate_bpm": 58,
  "hrv_ms": 42
}
```

#### `get_wellbeing`
Returns mindfulness and state of mind data for a given local date.

**Parameters:**
- `date` — local date string or natural string
- `timezone` — Olson timezone name (default: `Australia/Sydney`)

**Returns:**
```json
{
  "date": "2026-04-14",
  "mindful_minutes": 10,
  "state_of_mind": [
    {"time": "21:30", "valence": 4, "labels": ["calm", "grateful"]}
  ]
}
```

---

## Environment Variables

| Variable | Source | Description |
|---|---|---|
| `VAULT_PATH` | bind mount | Path to Obsidian vault (default: `/vault`) |
| `OWNTRACKS_URL` | `.env` | OwnTracks Recorder base URL |
| `OWNTRACKS_USER` | `.env` | OwnTracks username |
| `OWNTRACKS_DEVICE` | `.env` | OwnTracks device ID |
| `INFLUXDB_URL` | `.env` | InfluxDB base URL |
| `INFLUXDB_TOKEN` | `.env` | InfluxDB auth token |
| `INFLUXDB_ORG` | `.env` | InfluxDB org |
| `INFLUXDB_METRICS_BUCKET` | `.env` | Bucket for health metrics |
| `INFLUXDB_WORKOUTS_BUCKET` | `.env` | Bucket for workouts |
| `DEFAULT_TIMEZONE` | `.env` | Olson timezone (default: `Australia/Sydney`) |

---

## Docker Compose

Add to `docker-compose.ai.yml`:

```yaml
data-mcp:
  build:
    context: ./bede/data-mcp
  container_name: data-mcp
  restart: unless-stopped
  volumes:
    - ${VAULT_PATH}:/vault:ro
  environment:
    VAULT_PATH: /vault
    OWNTRACKS_URL: http://owntracks-recorder:8083
    OWNTRACKS_USER: ${OWNTRACKS_USER}
    OWNTRACKS_DEVICE: ${OWNTRACKS_DEVICE}
    INFLUXDB_URL: http://hae-influxdb:8086
    INFLUXDB_TOKEN: ${HAE_INFLUXDB_TOKEN}
    INFLUXDB_ORG: ${HAE_INFLUXDB_ORG}
    INFLUXDB_METRICS_BUCKET: ${HAE_INFLUXDB_METRICS_BUCKET}
    INFLUXDB_WORKOUTS_BUCKET: ${HAE_INFLUXDB_WORKOUTS_BUCKET}
    DEFAULT_TIMEZONE: Australia/Sydney
  expose:
    - 8000
  networks:
    - ai
    - homeserver
    - location
```

`VAULT_PATH` is the host path to the Obsidian vault git repo (already defined in
`.env` as the `VAULT_REPO` checkout location on the server).

The vault mount is read-only — `data-mcp` never writes to the vault.

Networks:
- `ai` — to be reachable by Bede
- `homeserver` — for InfluxDB
- `location` — for OwnTracks Recorder

---

## CLAUDE.md changes

Once `data-mcp` is live, the raw OwnTracks and InfluxDB connection details in
`bede/CLAUDE.md` are replaced with tool descriptions. Bede no longer needs to
know about UTC offsets, device UUIDs, Flux query syntax, or vault file paths —
just the tool names and what they return.

The Location Data and Health Data sections become a single short section listing
the available `personal-data` MCP tools.

---

## Repo boundary

`data-mcp` has no dependency on the dotfiles repo. The vault is the interface:
- dotfiles writes `data/daily-raw/YYYY-MM-DD/` files to the vault (Mac-side)
- `data-mcp` reads those files from `/vault/data/daily-raw/YYYY-MM-DD/` (server-side)

The path convention is the only contract between the two repos.

---

## Out of scope for v1

- Write tools (logging mood, adding notes) — read-only for now
- Persistent geocoding cache (in-memory per-process is sufficient initially)
- Multi-user support — single user assumed throughout
- Screen time data older than what's in the vault (no backfill)
