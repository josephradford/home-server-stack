# Granular Data Freshness — Design Spec

> **Status:** Approved — ready for implementation plan

## Goal

Replace bede-data's coarse "health"/"vault" freshness tracking with granular per-source freshness. Rename the "vault" ingest/API pipeline to "usage" (the Obsidian vault queue is unrelated and keeps its name).

## Schema Changes

### data_freshness table

Add `always_expected` column (INTEGER, default 1). Schema version 10 → 11.

Migration:
1. `ALTER TABLE data_freshness ADD COLUMN always_expected INTEGER NOT NULL DEFAULT 1`
2. `DELETE FROM data_freshness WHERE source IN ('health', 'vault')` — old coarse rows are replaced by granular sources on next ingest

### Freshness Sources

| Source key | Device | Pipeline | Expected interval (s) | Always expected |
|-----------|--------|----------|----------------------|-----------------|
| health_metrics | iPhone | HAE → /ingest/health | 1800 | Yes |
| sleep | iPhone | HAE → /ingest/health | 1800 | Yes |
| workouts | iPhone | HAE → /ingest/health | 1800 | Yes |
| medications | iPhone | HAE → /ingest/health | 1800 | Yes |
| state_of_mind | iPhone | HAE → /ingest/health | 1800 | Yes |
| screen_time_mac | Mac | usage-collect → /ingest/usage | 10800 | Yes |
| screen_time_iphone | iPhone | usage-collect → /ingest/usage | 10800 | Yes |
| safari_history | Mac + iPhone | usage-collect → /ingest/usage | 10800 | Yes |
| youtube_history | Mac + iPhone | usage-collect → /ingest/usage | 10800 | No |
| podcasts | Mac + iPhone | usage-collect → /ingest/usage | 10800 | No |
| claude_sessions | Mac | usage-collect → /ingest/usage | 10800 | No |
| bede_sessions | Mac | usage-collect → /ingest/usage | 10800 | No |
| owntracks | iPhone | live query | 3600 | Yes |

## Ingest Changes

### Health ingest (`POST /ingest/health`)

After `parse_health_payload` returns, call `_update_freshness` for each table that received rows. The parser already returns per-table insert counts — use those to determine which sources got data. Only update freshness for sources that had rows inserted/upserted.

`_update_freshness` gains an `always_expected` parameter (default True).

### Usage ingest (`POST /ingest/usage`, renamed from `/ingest/vault`)

After `parse_usage_upload` processes each file, call `_update_freshness` for that source. Map filenames to source keys:

| Filename | Source key | Always expected |
|----------|-----------|-----------------|
| screentime.csv | screen_time_mac | Yes |
| iphone-screentime.csv | screen_time_iphone | Yes |
| safari*.csv | safari_history | Yes |
| youtube*.csv | youtube_history | No |
| podcasts*.csv | podcasts | No |
| claude-sessions*.json | claude_sessions | No |
| bede-sessions*.json | bede_sessions | No |

Sources whose files are absent from the upload are not updated — Bede uses `always_expected=false` to know staleness means "no activity" rather than "pipeline broken".

## Freshness API Changes

### Stored sources

`GET /api/freshness` returns the same shape with `always_expected` added:

```json
{
  "sources": [
    {
      "source": "health_metrics",
      "last_received_at": "2026-05-10T08:30:00Z",
      "expected_interval_seconds": 1800,
      "always_expected": true,
      "updated_at": "2026-05-10T08:30:00Z"
    }
  ]
}
```

### OwnTracks (live-queried)

Query the owntracks-recorder `last` endpoint (`http://owntracks-recorder:8083/api/0/last`) at API call time. Extract the `tst` Unix timestamp. Include as a synthetic entry in the `sources` array:

```json
{
  "source": "owntracks",
  "last_received_at": "2026-05-10T09:15:00Z",
  "expected_interval_seconds": 3600,
  "always_expected": true,
  "updated_at": null
}
```

If the recorder is unreachable, omit the owntracks entry (don't fail the request). The OwnTracks recorder URL should come from config/env (OWNTRACKS_URL, defaulting to `http://owntracks-recorder:8083`).

## Rename: vault → usage

Rename the usage-collect ingest pipeline from "vault" to "usage". The Obsidian vault queue (`vault_queue.py`, `vault_publish_queue` table, `vault_path` column, `enqueue_vault_item` MCP tool) is a separate concept and keeps its name.

### bede-data renames

| Before | After |
|--------|-------|
| `POST /ingest/vault` | `POST /ingest/usage` |
| `GET /api/vault/*` | `GET /api/usage/*` |
| `ingest/vault_parser.py` | `ingest/usage_parser.py` |
| `parse_vault_payload()` | `parse_usage_payload()` |
| `api/vault_data.py` | `api/usage_data.py` |
| `vault_data_router` | `usage_data_router` |
| `tests/test_ingest_vault.py` | `tests/test_ingest_usage.py` |
| `tests/test_api_vault_data.py` | `tests/test_api_usage_data.py` |

### bede-data-mcp renames

| Before | After |
|--------|-------|
| `/api/vault/screen-time` → | `/api/usage/screen-time` |
| `/api/vault/safari` → | `/api/usage/safari` |
| `/api/vault/youtube` → | `/api/usage/youtube` |
| `/api/vault/podcasts` → | `/api/usage/podcasts` |
| `/api/vault/claude-sessions` → | `/api/usage/claude-sessions` |
| `/api/vault/bede-sessions` → | `/api/usage/bede-sessions` |
| `tests/test_vault_tools.py` | `tests/test_usage_tools.py` |

### dotfiles renames

| Before | After |
|--------|-------|
| `usage-collect.sh`: `/ingest/vault` | `/ingest/usage` |
| `CLAUDE.md` reference to `/ingest/vault` | `/ingest/usage` |

### Documentation updates

- `bede-data/docs/data-sources.md` — endpoint references
- `home-server-stack/SERVICES.md` — if it references the vault endpoint
- `home-server-stack/docs/superpowers/specs/2026-05-10-granular-data-freshness.md` — update status

## Testing

- Update `test_api_freshness.py` — test granular source keys, `always_expected` field, OwnTracks live entry
- Update renamed test files for new module/function names
- Update `test_db.py` if it tests freshness schema
- Verify `make validate` passes in home-server-stack

## Not in scope

- `music_listens` — not yet implemented in usage-collect
- Changes to bede-core or bede-core's vault mount (that's the Obsidian vault, different concept)
- `vault_queue.py`, `vault_publish_queue` table — Obsidian vault publishing, not usage data
