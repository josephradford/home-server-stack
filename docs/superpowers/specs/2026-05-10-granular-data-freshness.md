# Granular Data Freshness — Design Notes

> **Status:** Research / brainstorming — not yet a spec. Resume from here when ready to implement.

## Problem

bede-data currently tracks two freshness sources: `health` and `vault`. This is too coarse — Bede can't tell the user "your sleep data hasn't synced" vs "your screen time collection didn't run" because both are lumped together.

## Current Implementation

- `data_freshness` SQLite table with columns: `source`, `last_received_at`, `expected_interval_seconds`
- `_update_freshness(conn, "health", 86400)` called once per health ingest POST
- `_update_freshness(conn, "vault", 86400)` called once per usage-collect ingest POST
- `get_data_freshness()` API returns all rows from the table
- Key files: `bede-data/src/bede_data/ingest/router.py`, `bede-data/src/bede_data/api/freshness.py`

## Data Sources

### Health (iPhone → HAE app → bede-data)

Apple Health Auto Export (HAE) runs **6 separate automations**, each POSTing independently every 30 minutes. Documented in `bede-data/docs/hae-setup.md`.

| Automation | Data | Expected interval |
|-----------|------|-------------------|
| Health metrics | Steps, active energy, HRV, resting HR, etc. | 30min |
| Health metrics (day grouping) | Daily aggregates | 30min |
| Sleep metrics | Bedtime, wake time, duration | 30min |
| Workouts | Type, duration, calories | 30min |
| State of mind | Mood/wellbeing entries | 30min |
| Medications | Medication log | 30min |

Each automation always fires regardless of whether there's new data. The payload may contain entries already in the DB (upserted/skipped). So freshness can always be updated on receipt — a stale health source reliably means the pipeline is broken.

### Usage-collect (Mac → usage-collect.sh → bede-data)

The `usage-collect.sh` launchd agent runs at 13 scheduled times throughout the day (8am–11pm, irregular intervals, worst-case gap 3h). It collects usage and activity data from the Mac (and iPhone via iCloud-synced databases) and POSTs a JSON payload to `/ingest/vault`. Plist: `dotfiles/launchd/com.joeradford.usage-collect.plist`.

macOS `StartCalendarInterval` fires on wake for missed intervals, so if the Mac was asleep all morning, it catches up.

The script only includes files that exist in the upload. The parser (`bede_data/ingest/vault_parser.py`) routes by filename:

| File | Source name | Device | Notes |
|------|------------|--------|-------|
| `screentime.csv` | screen_time_mac | Mac | Always collected |
| `iphone-screentime.csv` | screen_time_iphone | iPhone | Always collected (via Biome on Mac) |
| `safari*.csv` | safari_history | Mac + iPhone | Always collected |
| `youtube*.csv` | youtube_history | Mac + iPhone | Only if there were YouTube visits |
| `podcasts*.csv` | podcasts | Mac + iPhone | Only if podcasts were played |
| `claude-sessions*.json` | claude_sessions | Mac | Only if Claude Code was used |
| `bede-sessions*.json` | bede_sessions | Mac | Only if Bede conversations happened |

**Key distinction:** Some files are always present (screen time, Safari) and some are only included when there's activity. A missing file could mean "no activity" or "collection failed" — we can't distinguish these from the ingest side alone.

**iCloud sync pattern:** Safari, YouTube, and Podcasts cover both Mac and iPhone because their underlying macOS databases (History.db, MTLibrary.sqlite) sync from iPhone via iCloud. Screen time does NOT — it uses two independent pipelines (knowledgeC.db for Mac, Biome SEGB for iPhone), which is why it's split into separate freshness sources.

### OwnTracks (iPhone → owntracks-recorder)

OwnTracks has its own file-based data store — not in our SQLite. Location data is already live-queried via HTTP API (`bede_data/live/location.py`). The recorder's `last` endpoint returns a JSON file with a `tst` Unix timestamp for the most recent location point.

Freshness for OwnTracks should be computed live by querying the recorder, not tracked in our `data_freshness` table. This matches the existing pattern — we don't ingest OwnTracks data, we proxy it.

## Proposed Freshness Sources

| Source key | Device | Pipeline | Expected interval | Always expected? |
|-----------|--------|----------|-------------------|-----------------|
| health_metrics | iPhone | HAE | 30min | Yes |
| sleep | iPhone | HAE | 30min | Yes |
| workouts | iPhone | HAE | 30min | Yes |
| medications | iPhone | HAE | 30min | Yes |
| state_of_mind | iPhone | HAE | 30min | Yes |
| screen_time_mac | Mac | usage-collect | 3h | Yes |
| screen_time_iphone | iPhone | usage-collect | 3h | Yes |
| safari_history | Mac + iPhone | usage-collect | 3h | Yes |
| youtube_history | Mac + iPhone | usage-collect | 3h | No — no data = no YouTube visits |
| podcasts | Mac + iPhone | usage-collect | 3h | No — no data = no podcasts played |
| claude_sessions | Mac | usage-collect | 3h | No — no data = no Claude usage |
| bede_sessions | Mac | usage-collect | 3h | No — no data = no Bede conversations |
| owntracks | iPhone | live query | 1h | Yes |

## Recommended Approach

Expand the existing `data_freshness` table with granular source keys. Update freshness at ingest time per sub-source rather than per pipeline.

- **Health ingest**: after parsing, update freshness for each table that received data
- **Mac-collect ingest**: after parsing each file, update freshness for that source. Only update sources whose files were included in the upload
- **OwnTracks**: query the recorder's `last` endpoint at API call time. Return `tst` as the freshness timestamp inline with the stored sources
- **"Always expected" flag**: add a column or metadata so Bede knows whether staleness means "pipeline broken" (screen time) vs "no activity" (podcasts)

### Open question

For "always expected = no" sources: should freshness be updated when the usage-collect pipeline runs but the file wasn't included? This would let Bede distinguish "pipeline ran, no activity" from "pipeline didn't run". Trade-off: requires the ingest endpoint to know which files *could* have been sent, not just which ones *were* sent. Simplest answer may be to just not update those sources and let Bede use the "always expected" flag to interpret staleness.

## Not Yet Decided

- Exact schema changes (new columns vs. new table)
- API response format changes
- Migration path from current two-source system
- Whether CLAUDE.md.example needs richer freshness documentation for Bede
- MCP tool changes (if any)
