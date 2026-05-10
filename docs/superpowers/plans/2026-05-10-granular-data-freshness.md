# Granular Data Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace bede-data's coarse "health"/"vault" freshness tracking with 13 granular per-source entries, rename the "vault" pipeline to "usage", and add live OwnTracks freshness.

**Architecture:** Extend the existing `data_freshness` table with an `always_expected` column (schema v11). Update health and usage ingest endpoints to call `_update_freshness` per sub-source instead of once per pipeline. Add live OwnTracks freshness to the API response by querying the recorder. Rename all "vault" ingest/API references to "usage" across bede-data, bede-data-mcp, and dotfiles.

**Tech Stack:** Python/FastAPI, SQLite, pytest, shell (zsh)

**Repos:** Changes span three repos:
- `bede` (`/Users/joeradford/dev/bede`) — bede-data and bede-data-mcp packages
- `home-server-stack` (`/Users/joeradford/dev/home-server-stack`) — SERVICES.md, docs
- `dotfiles` (`/Users/joeradford/dev/dotfiles`) — usage-collect.sh

---

### Task 1: Schema — add `always_expected` column and bump to v11

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/db/schema.py:1` (SCHEMA_VERSION)
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/db/schema.py:285-290` (data_freshness DDL)
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/db/connection.py:52-62` (migration block)
- Test: `/Users/joeradford/dev/bede/bede-data/tests/test_db.py`

- [ ] **Step 1: Write failing test for schema v11 and always_expected column**

In `/Users/joeradford/dev/bede/bede-data/tests/test_db.py`, update the schema version test and add a new test:

```python
# Change existing test
def test_schema_version_is_set(db):
    cursor = db.execute("SELECT MAX(version) FROM schema_version")
    version = cursor.fetchone()[0]
    assert version == 11


def test_data_freshness_has_always_expected_column(db):
    cols = {row[1] for row in db.execute("PRAGMA table_info(data_freshness)").fetchall()}
    assert "always_expected" in cols
    db.execute(
        "INSERT INTO data_freshness (source, last_received_at, expected_interval_seconds, always_expected) VALUES (?, ?, ?, ?)",
        ("test_source", "2026-05-10T00:00:00Z", 1800, 1),
    )
    db.commit()
    row = db.execute("SELECT always_expected FROM data_freshness WHERE source = 'test_source'").fetchone()
    assert row["always_expected"] == 1


def test_data_freshness_always_expected_defaults_to_true(db):
    db.execute(
        "INSERT INTO data_freshness (source, last_received_at, expected_interval_seconds) VALUES (?, ?, ?)",
        ("test_default", "2026-05-10T00:00:00Z", 1800),
    )
    db.commit()
    row = db.execute("SELECT always_expected FROM data_freshness WHERE source = 'test_default'").fetchone()
    assert row["always_expected"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_db.py::test_schema_version_is_set bede-data/tests/test_db.py::test_data_freshness_has_always_expected_column bede-data/tests/test_db.py::test_data_freshness_always_expected_defaults_to_true -v`
Expected: FAIL — schema version is 10, column doesn't exist

- [ ] **Step 3: Update schema DDL and version**

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/db/schema.py`:

Change line 1:
```python
SCHEMA_VERSION = 11
```

Change the data_freshness DDL (lines 285-290):
```sql
CREATE TABLE IF NOT EXISTS data_freshness (
    source                   TEXT PRIMARY KEY,
    last_received_at         TEXT NOT NULL,
    expected_interval_seconds INTEGER NOT NULL,
    always_expected          INTEGER NOT NULL DEFAULT 1,
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Add migration for existing DBs (v10 → v11)**

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/db/connection.py`, add after the `existing < 8` block (after line 62):

```python
        if existing is not None and existing < 11:
            try:
                conn.execute(
                    "ALTER TABLE data_freshness ADD COLUMN always_expected INTEGER NOT NULL DEFAULT 1"
                )
            except sqlite3.OperationalError:
                pass
            conn.execute("DELETE FROM data_freshness WHERE source IN ('health', 'vault')")
            conn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_db.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/db/schema.py bede-data/src/bede_data/db/connection.py bede-data/tests/test_db.py
git commit -m "feat(bede-data): add always_expected column to data_freshness, bump schema to v11"
```

---

### Task 2: Granular health freshness

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/router.py:45-68`
- Test: `/Users/joeradford/dev/bede/bede-data/tests/test_api_freshness.py`

- [ ] **Step 1: Write failing test for granular health freshness**

In `/Users/joeradford/dev/bede/bede-data/tests/test_api_freshness.py`, replace the existing `test_get_freshness_with_data` test and add a new integration test:

```python
def test_get_freshness_with_data(client, db):
    db.execute(
        "INSERT INTO data_freshness (source, last_received_at, expected_interval_seconds, always_expected) VALUES (?, ?, ?, ?)",
        ("health_metrics", "2026-04-29T08:00:00Z", 1800, 1),
    )
    db.execute(
        "INSERT INTO data_freshness (source, last_received_at, expected_interval_seconds, always_expected) VALUES (?, ?, ?, ?)",
        ("screen_time_mac", "2026-04-29T06:00:00Z", 10800, 1),
    )
    db.commit()

    response = client.get("/api/freshness")
    data = response.json()
    assert len(data["sources"]) == 2
    assert all(
        "source" in s and "last_received_at" in s and "always_expected" in s
        for s in data["sources"]
    )


def test_health_ingest_updates_granular_freshness(client, db):
    from bede_data.config import settings

    settings.ingest_write_token = "test-token"
    payload = {
        "data": {
            "metrics": [
                {
                    "name": "step_count",
                    "data": [
                        {
                            "date": "2026-05-10 00:00:00 +1000",
                            "qty": 8000,
                            "source": "Apple Watch",
                        }
                    ],
                }
            ]
        }
    }
    response = client.post(
        "/ingest/health",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200

    cursor = db.execute(
        "SELECT source, expected_interval_seconds, always_expected FROM data_freshness ORDER BY source"
    )
    sources = {row["source"]: row for row in cursor.fetchall()}
    assert "health_metrics" in sources
    assert sources["health_metrics"]["expected_interval_seconds"] == 1800
    assert sources["health_metrics"]["always_expected"] == 1
    assert "health" not in sources
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_api_freshness.py -v`
Expected: FAIL — `test_health_ingest_updates_granular_freshness` fails because ingest still writes "health" with 86400

- [ ] **Step 3: Update `_update_freshness` and health ingest**

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/router.py`:

Update `_update_freshness` (lines 45-51) to accept `always_expected`:
```python
def _update_freshness(
    conn: sqlite3.Connection, source: str, expected_interval: int, *, always_expected: bool = True
):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        """INSERT OR REPLACE INTO data_freshness
           (source, last_received_at, expected_interval_seconds, always_expected, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (source, now, expected_interval, int(always_expected), now),
    )
```

Update `ingest_health` (lines 54-69) to update per-table freshness:
```python
@router.post("/health")
def ingest_health(
    payload: dict,
    _token: str = Depends(verify_ingest_token),
    conn: sqlite3.Connection = Depends(get_db),
):
    parsed = parse_health_payload(payload)
    total = 0
    counts = {}
    for table in ("health_metrics", "sleep_phases", "workouts", "medications", "state_of_mind"):
        n = _upsert_rows(conn, table, parsed[table])
        total += n
        counts[table] = n
    _HEALTH_SOURCE_KEYS = {
        "health_metrics": "health_metrics",
        "sleep_phases": "sleep",
        "workouts": "workouts",
        "medications": "medications",
        "state_of_mind": "state_of_mind",
    }
    for table, source_key in _HEALTH_SOURCE_KEYS.items():
        if counts[table] > 0:
            _update_freshness(conn, source_key, 1800)
    conn.commit()
    return {"status": "ok", "records": total}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_api_freshness.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/ingest/router.py bede-data/tests/test_api_freshness.py
git commit -m "feat(bede-data): granular per-table freshness for health ingest"
```

---

### Task 3: Rename vault → usage (bede-data)

**Files:**
- Rename: `bede-data/src/bede_data/ingest/vault_parser.py` → `usage_parser.py`
- Rename: `bede-data/src/bede_data/api/vault_data.py` → `usage_data.py`
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/router.py:9,72-96`
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/app.py:22,40`
- Rename: `bede-data/tests/test_ingest_vault.py` → `test_ingest_usage.py`
- Rename: `bede-data/tests/test_api_vault_data.py` → `test_api_usage_data.py`

- [ ] **Step 1: Rename parser module and update function name**

```bash
cd /Users/joeradford/dev/bede
git mv bede-data/src/bede_data/ingest/vault_parser.py bede-data/src/bede_data/ingest/usage_parser.py
```

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/usage_parser.py`, rename the public function (line 148):

```python
def parse_usage_payload(payload: dict) -> dict:
    """Parse a usage ingest payload containing {date, files: {filename: content}}. Files are routed by filename prefix to the appropriate CSV or markdown parser."""
```

- [ ] **Step 2: Rename API module and update prefix**

```bash
cd /Users/joeradford/dev/bede
git mv bede-data/src/bede_data/api/vault_data.py bede-data/src/bede_data/api/usage_data.py
```

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/api/usage_data.py`, update the router prefix (line 11):

```python
router = APIRouter(prefix="/api/usage", tags=["usage"])
```

- [ ] **Step 3: Update router.py imports and endpoint**

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/router.py`:

Update import (line 9):
```python
from bede_data.ingest.usage_parser import parse_usage_payload
```

Update endpoint (lines 72-96):
```python
@router.post("/usage")
def ingest_usage(
    payload: dict,
    _token: str = Depends(verify_ingest_token),
    conn: sqlite3.Connection = Depends(get_db),
):
    parsed = parse_usage_payload(payload)
```

- [ ] **Step 4: Update app.py imports and registration**

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/app.py`:

Update import (line 22):
```python
from bede_data.api.usage_data import router as usage_data_router
```

Update registration (line 40):
```python
    app.include_router(usage_data_router)
```

- [ ] **Step 5: Rename test files and update references**

```bash
cd /Users/joeradford/dev/bede
git mv bede-data/tests/test_ingest_vault.py bede-data/tests/test_ingest_usage.py
git mv bede-data/tests/test_api_vault_data.py bede-data/tests/test_api_usage_data.py
```

In `/Users/joeradford/dev/bede/bede-data/tests/test_ingest_usage.py`:

Update import (line 2):
```python
from bede_data.ingest.usage_parser import parse_usage_payload
```

Replace all `parse_vault_payload` with `parse_usage_payload` (5 occurrences).

Replace all `"/ingest/vault"` with `"/ingest/usage"` (3 occurrences).

In `/Users/joeradford/dev/bede/bede-data/tests/test_api_usage_data.py`:

Replace all `"/api/vault/` with `"/api/usage/` (all endpoint references — 15 occurrences).

- [ ] **Step 6: Run all tests to verify renames work**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/joeradford/dev/bede
git add -A bede-data/
git commit -m "refactor(bede-data): rename vault to usage across ingest, API, and tests"
```

---

### Task 4: Granular usage freshness

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/router.py:72-96`
- Test: `/Users/joeradford/dev/bede/bede-data/tests/test_ingest_usage.py`

- [ ] **Step 1: Write failing test for granular usage freshness**

Add to `/Users/joeradford/dev/bede/bede-data/tests/test_ingest_usage.py`:

```python
def test_ingest_usage_updates_granular_freshness(client, db):
    settings.ingest_write_token = "test-token"
    payload = {
        "date": "2026-04-29",
        "files": {
            "screentime.csv": "device,entry_type,name,seconds\nmac,app,Safari,3600\n",
            "iphone-screentime.csv": "device,entry_type,name,seconds\niphone,app,Instagram,2400\n",
            "safari-pages.csv": "device,domain,title,url,visited_at\nmac,github.com,GitHub,https://github.com,2026-04-29T10:00:00Z\n",
            "youtube.csv": "title,url,visited_at\nCool Video,https://youtube.com/watch?v=abc,2026-04-29T14:00:00Z\n",
        },
    }
    response = client.post(
        "/ingest/usage",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200

    cursor = db.execute(
        "SELECT source, expected_interval_seconds, always_expected FROM data_freshness ORDER BY source"
    )
    sources = {row["source"]: dict(row) for row in cursor.fetchall()}

    assert "screen_time_mac" in sources
    assert sources["screen_time_mac"]["expected_interval_seconds"] == 10800
    assert sources["screen_time_mac"]["always_expected"] == 1

    assert "screen_time_iphone" in sources
    assert sources["screen_time_iphone"]["always_expected"] == 1

    assert "safari_history" in sources
    assert sources["safari_history"]["always_expected"] == 1

    assert "youtube_history" in sources
    assert sources["youtube_history"]["always_expected"] == 0

    assert "vault" not in sources


def test_ingest_usage_skips_freshness_for_absent_optional_sources(client, db):
    settings.ingest_write_token = "test-token"
    payload = {
        "date": "2026-04-29",
        "files": {
            "screentime.csv": "device,entry_type,name,seconds\nmac,app,Safari,3600\n",
        },
    }
    client.post(
        "/ingest/usage",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )

    cursor = db.execute("SELECT source FROM data_freshness ORDER BY source")
    sources = [row["source"] for row in cursor.fetchall()]
    assert "screen_time_mac" in sources
    assert "youtube_history" not in sources
    assert "podcasts" not in sources
    assert "claude_sessions" not in sources
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_ingest_usage.py::test_ingest_usage_updates_granular_freshness bede-data/tests/test_ingest_usage.py::test_ingest_usage_skips_freshness_for_absent_optional_sources -v`
Expected: FAIL — still writes single "vault" freshness entry (or "usage" after Task 3 rename, but not granular)

- [ ] **Step 3: Implement per-file freshness in usage ingest**

In `/Users/joeradford/dev/bede/bede-data/src/bede_data/ingest/router.py`, replace the usage ingest function:

```python
_USAGE_FRESHNESS = {
    "screen_time_mac": {"files": {"screentime.csv"}, "always_expected": True},
    "screen_time_iphone": {"files": {"iphone-screentime.csv"}, "always_expected": True},
    "safari_history": {"prefix": "safari", "always_expected": True},
    "youtube_history": {"prefix": "youtube", "always_expected": False},
    "podcasts": {"prefix": "podcasts", "always_expected": False},
    "claude_sessions": {"prefix": "claude-sessions", "always_expected": False},
    "bede_sessions": {"prefix": "bede-sessions", "always_expected": False},
}


def _usage_sources_present(files: dict[str, str]) -> set[str]:
    """Return the set of freshness source keys whose files appear in the upload."""
    present = set()
    filenames = set(files.keys())
    for source_key, spec in _USAGE_FRESHNESS.items():
        if "files" in spec:
            if spec["files"] & filenames:
                present.add(source_key)
        elif "prefix" in spec:
            if any(f.startswith(spec["prefix"]) for f in filenames):
                present.add(source_key)
    return present


@router.post("/usage")
def ingest_usage(
    payload: dict,
    _token: str = Depends(verify_ingest_token),
    conn: sqlite3.Connection = Depends(get_db),
):
    parsed = parse_usage_payload(payload)
    date = payload.get("date", "")
    total = 0

    if parsed["screen_time"]:
        devices = {r["device"] for r in parsed["screen_time"]}
        for device in devices:
            device_rows = [r for r in parsed["screen_time"] if r["device"] == device]
            total += _replace_daily(conn, "screen_time", date, device, device_rows)

    total += _upsert_rows(conn, "safari_history", parsed["safari_history"])
    total += _upsert_rows(conn, "youtube_history", parsed["youtube_history"])
    total += _upsert_rows(conn, "podcasts", parsed["podcasts"])
    total += _upsert_rows(conn, "claude_sessions", parsed["claude_sessions"])
    total += _upsert_rows(conn, "bede_sessions", parsed["bede_sessions"])
    total += _upsert_rows(conn, "music_listens", parsed.get("music_listens", []))

    for source_key in _usage_sources_present(payload.get("files", {})):
        spec = _USAGE_FRESHNESS[source_key]
        _update_freshness(conn, source_key, 10800, always_expected=spec["always_expected"])

    conn.commit()
    return {"status": "ok", "records": total}
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/ingest/router.py bede-data/tests/test_ingest_usage.py
git commit -m "feat(bede-data): granular per-file freshness for usage ingest"
```

---

### Task 5: Freshness API — add `always_expected` and live OwnTracks

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-data/src/bede_data/api/freshness.py`
- Test: `/Users/joeradford/dev/bede/bede-data/tests/test_api_freshness.py`

- [ ] **Step 1: Write failing tests for updated API response**

Add to `/Users/joeradford/dev/bede/bede-data/tests/test_api_freshness.py`:

```python
def test_freshness_includes_always_expected_field(client, db):
    db.execute(
        "INSERT INTO data_freshness (source, last_received_at, expected_interval_seconds, always_expected) VALUES (?, ?, ?, ?)",
        ("youtube_history", "2026-05-10T08:00:00Z", 10800, 0),
    )
    db.commit()

    response = client.get("/api/freshness")
    sources = response.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["always_expected"] == 0


def test_freshness_includes_owntracks(client, db, monkeypatch):
    import httpx

    mock_response = httpx.Response(
        200,
        json=[{"tst": 1715320500, "_type": "location"}],
    )
    monkeypatch.setattr(
        "httpx.get", lambda *args, **kwargs: mock_response
    )

    response = client.get("/api/freshness")
    sources = {s["source"]: s for s in response.json()["sources"]}
    assert "owntracks" in sources
    assert sources["owntracks"]["expected_interval_seconds"] == 3600
    assert sources["owntracks"]["always_expected"] == 1
    assert sources["owntracks"]["updated_at"] is None


def test_freshness_omits_owntracks_when_recorder_unreachable(client, db, monkeypatch):
    import httpx

    def raise_error(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("httpx.get", raise_error)

    response = client.get("/api/freshness")
    assert response.status_code == 200
    sources = [s["source"] for s in response.json()["sources"]]
    assert "owntracks" not in sources
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_api_freshness.py -v`
Expected: FAIL — `always_expected` not in SELECT, no OwnTracks entry

- [ ] **Step 3: Update freshness API endpoint**

Replace `/Users/joeradford/dev/bede/bede-data/src/bede_data/api/freshness.py`:

```python
import sqlite3
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends

from bede_data.config import settings
from bede_data.db.connection import get_db

router = APIRouter(prefix="/api/freshness", tags=["freshness"])


def _fetch_owntracks_freshness() -> dict | None:
    try:
        resp = httpx.get(
            f"{settings.owntracks_url}/api/0/last",
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            tst = data[0].get("tst")
        elif isinstance(data, dict):
            tst = data.get("tst")
        else:
            return None
        if tst is None:
            return None
        last_received = datetime.fromtimestamp(tst, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return {
            "source": "owntracks",
            "last_received_at": last_received,
            "expected_interval_seconds": 3600,
            "always_expected": 1,
            "updated_at": None,
        }
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


@router.get("")
def get_freshness(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.execute(
        "SELECT source, last_received_at, expected_interval_seconds, always_expected, updated_at FROM data_freshness ORDER BY source"
    )
    sources = [dict(r) for r in cursor.fetchall()]

    owntracks = _fetch_owntracks_freshness()
    if owntracks is not None:
        sources.append(owntracks)
        sources.sort(key=lambda s: s["source"])

    return {"sources": sources}
```

- [ ] **Step 4: Add httpx to bede-data dependencies (if not already present)**

Run: `cd /Users/joeradford/dev/bede && grep httpx bede-data/pyproject.toml`

If httpx is already a dependency (it likely is — used by location.py), skip. If not:
```bash
cd /Users/joeradford/dev/bede/bede-data && uv add httpx
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/test_api_freshness.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/api/freshness.py bede-data/tests/test_api_freshness.py
git commit -m "feat(bede-data): add always_expected to freshness API, live OwnTracks freshness"
```

---

### Task 6: Rename vault → usage in bede-data-mcp

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-data-mcp/src/bede_data_mcp/server.py:192,219,230,245,256,267`
- Rename: `bede-data-mcp/tests/test_vault_tools.py` → `test_usage_tools.py`

- [ ] **Step 1: Update API paths in MCP server**

In `/Users/joeradford/dev/bede/bede-data-mcp/src/bede_data_mcp/server.py`, replace all `/api/vault/` with `/api/usage/` (6 occurrences):

- Line 192: `"/api/vault/screen-time"` → `"/api/usage/screen-time"`
- Line 219: `"/api/vault/safari"` → `"/api/usage/safari"`
- Line 230: `"/api/vault/youtube"` → `"/api/usage/youtube"`
- Line 245: `"/api/vault/podcasts"` → `"/api/usage/podcasts"`
- Line 256: `"/api/vault/claude-sessions"` → `"/api/usage/claude-sessions"`
- Line 267: `"/api/vault/bede-sessions"` → `"/api/usage/bede-sessions"`

- [ ] **Step 2: Rename test file and update assertions**

```bash
cd /Users/joeradford/dev/bede
git mv bede-data-mcp/tests/test_vault_tools.py bede-data-mcp/tests/test_usage_tools.py
```

In `/Users/joeradford/dev/bede/bede-data-mcp/tests/test_usage_tools.py`, replace all `"/api/vault/` with `"/api/usage/` (6 occurrences):

- Line 18: `"/api/vault/screen-time"` → `"/api/usage/screen-time"`
- Line 27: `"/api/vault/screen-time"` → `"/api/usage/screen-time"`
- Line 42: `"/api/vault/safari"` → `"/api/usage/safari"`
- Line 53: `"/api/vault/safari"` → `"/api/usage/safari"`
- Line 69: `"/api/vault/youtube"` → `"/api/usage/youtube"`
- Line 88: `"/api/vault/podcasts"` → `"/api/usage/podcasts"`
- Line 100: `"/api/vault/claude-sessions"` → `"/api/usage/claude-sessions"`
- Line 112: `"/api/vault/bede-sessions"` → `"/api/usage/bede-sessions"`

- [ ] **Step 3: Run MCP tests to verify**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data-mcp/tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
cd /Users/joeradford/dev/bede
git add -A bede-data-mcp/
git commit -m "refactor(bede-data-mcp): rename vault API paths to usage"
```

---

### Task 7: Update dotfiles — usage-collect.sh endpoint

**Files:**
- Modify: `/Users/joeradford/dev/dotfiles/scripts/usage-collect.sh:17,36`

- [ ] **Step 1: Update endpoint references in usage-collect.sh**

In `/Users/joeradford/dev/dotfiles/scripts/usage-collect.sh`:

Line 17 — update comment:
```
# Data destination: POST https://data.DOMAIN/ingest/usage with Bearer token auth.
```

Line 36 — update example:
```
#   INGEST_URL=https://data.example.com/ingest/usage
```

- [ ] **Step 2: Verify no other vault references remain**

Run: `cd /Users/joeradford/dev/dotfiles && grep -rn "vault" scripts/usage-collect.sh`
Expected: No output

- [ ] **Step 3: Commit**

```bash
cd /Users/joeradford/dev/dotfiles
git add scripts/usage-collect.sh
git commit -m "refactor: update ingest endpoint from /ingest/vault to /ingest/usage"
```

Note: The actual `INGEST_URL` value is set in `dotfiles/.env` (not committed). The user must update the `.env` file on the Mac to point to `/ingest/usage` before deploying bede-data. Remind the user of this at completion.

---

### Task 8: Update bede-web freshness card — group by pipeline

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-web/src/index.html:15-33` (freshness card template)
- Modify: `/Users/joeradford/dev/bede/bede-web/src/index.html:97,125,142-149` (JS data + freshnessColor)
- Modify: `/Users/joeradford/dev/bede/bede-web/src/css/app.css` (add muted status color)

- [ ] **Step 1: Add muted status color for optional sources**

In `/Users/joeradford/dev/bede/bede-web/src/css/app.css`, add a muted color variable:

```css
  --color-status-muted: #6b7280;
```

Add it after the `--color-status-pending` line.

- [ ] **Step 2: Replace the freshness card template**

In `/Users/joeradford/dev/bede/bede-web/src/index.html`, replace lines 15-33 (the entire Data Freshness card) with:

```html
      <!-- Data Freshness -->
      <div class="bg-surface-card border border-surface-border rounded-lg p-4">
        <h2 class="text-xs uppercase text-gray-500 mb-3">Data Freshness</h2>
        <template x-if="error">
          <p class="text-status-error text-sm" x-text="error"></p>
        </template>
        <template x-for="group in freshnessGroups" :key="group.label">
          <div class="mb-3 last:mb-0">
            <h3 class="text-[10px] uppercase text-gray-600 mb-1" x-text="group.label"></h3>
            <div class="space-y-1">
              <template x-for="src in group.sources" :key="src.source">
                <div class="flex items-center justify-between text-sm">
                  <span class="flex items-center gap-2">
                    <span class="w-2 h-2 rounded-full" :class="freshnessColor(src)"></span>
                    <span x-text="sourceLabel(src.source)"></span>
                  </span>
                  <span class="text-gray-500 text-xs" x-text="timeAgo(src.last_received_at)"></span>
                </div>
              </template>
            </div>
          </div>
        </template>
      </div>
```

- [ ] **Step 3: Update JS — add grouping, labels, and updated color logic**

In `/Users/joeradford/dev/bede/bede-web/src/index.html`, in the `dashboard()` function:

Add `freshnessGroups` as a computed property. Replace the `freshness` assignment in `refresh()` (line 125) and add helper functions.

Replace `this.freshness = freshRes.data.sources;` with:
```javascript
          this.freshness = freshRes.data.sources;
          this.freshnessGroups = this.groupFreshness(freshRes.data.sources);
```

Add `freshnessGroups: [],` after `freshness: [],` (line 97).

Add these methods to the dashboard object (after `timeAgo`):

```javascript
        sourceLabel(source) {
          const labels = {
            health_metrics: "Metrics",
            sleep: "Sleep",
            workouts: "Workouts",
            medications: "Medications",
            state_of_mind: "Wellbeing",
            screen_time_mac: "Screen Time (Mac)",
            screen_time_iphone: "Screen Time (iPhone)",
            safari_history: "Safari",
            youtube_history: "YouTube",
            podcasts: "Podcasts",
            claude_sessions: "Claude",
            bede_sessions: "Bede",
            owntracks: "Location",
          };
          return labels[source] || source;
        },

        groupFreshness(sources) {
          const groups = {
            "Health": ["health_metrics", "sleep", "workouts", "medications", "state_of_mind"],
            "Usage": ["screen_time_mac", "screen_time_iphone", "safari_history", "youtube_history", "podcasts", "claude_sessions", "bede_sessions"],
            "Location": ["owntracks"],
          };
          return Object.entries(groups)
            .map(([label, keys]) => ({
              label,
              sources: keys.map(k => sources.find(s => s.source === k)).filter(Boolean),
            }))
            .filter(g => g.sources.length > 0);
        },
```

Update `freshnessColor` to handle optional sources:

```javascript
        freshnessColor(src) {
          if (!src.last_received_at) return "bg-status-error";
          const age = (Date.now() - new Date(src.last_received_at).getTime()) / 1000;
          const expected = src.expected_interval_seconds || 86400;
          if (age <= expected) return "bg-status-ok";
          if (age <= expected * 2) return "bg-status-warn";
          if (!src.always_expected) return "bg-status-muted";
          return "bg-status-error";
        },
```

- [ ] **Step 4: Visually verify in browser**

Run: `cd /Users/joeradford/dev/bede/bede-web && npm run dev` (or equivalent dev server)
Check that:
- Sources are grouped under Health, Usage, Location headings
- Labels are human-readable (e.g. "Screen Time (Mac)" not "screen_time_mac")
- Always-expected sources show red when stale, optional sources show grey

- [ ] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-web/src/index.html bede-web/src/css/app.css
git commit -m "feat(bede-web): group freshness by pipeline, add labels and muted status for optional sources"
```

---

### Task 9: Update documentation

**Files:**
- Modify: `/Users/joeradford/dev/bede/bede-data/docs/data-sources.md:26`
- Modify: `/Users/joeradford/dev/home-server-stack/SERVICES.md:106`

- [ ] **Step 1: Update data-sources.md**

In `/Users/joeradford/dev/bede/bede-data/docs/data-sources.md`, line 26:

```
Source: `usage-collect.sh` launchd agent on the Mac. Runs 13 times daily (8am–11pm, irregular intervals, worst-case gap 3h). Endpoint: `POST /ingest/usage`.
```

- [ ] **Step 2: Update SERVICES.md**

In `/Users/joeradford/dev/home-server-stack/SERVICES.md`, line 106:

Replace `vault` with `usage`:
```
- **Purpose:** Data layer for Bede — REST API serving health, location, usage, memory, goal, analytics, config, deal monitoring, and news curation data from SQLite
```

- [ ] **Step 3: Update original spec status**

In `/Users/joeradford/dev/home-server-stack/docs/superpowers/specs/2026-05-10-granular-data-freshness.md`, line 3:

```
> **Status:** Implemented — see design spec and implementation plan in `docs/superpowers/specs/` and `docs/superpowers/plans/`.
```

- [ ] **Step 4: Commit in each repo**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/docs/data-sources.md
git commit -m "docs(bede-data): update ingest endpoint reference to /ingest/usage"

cd /Users/joeradford/dev/home-server-stack
git add SERVICES.md docs/superpowers/specs/2026-05-10-granular-data-freshness.md
git commit -m "docs: update vault references to usage, mark freshness spec as implemented"
```

---

### Task 10: Final verification — run full test suites

**Files:** None (verification only)

- [ ] **Step 1: Run full bede-data test suite**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data/tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run full bede-data-mcp test suite**

Run: `cd /Users/joeradford/dev/bede && python -m pytest bede-data-mcp/tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Validate home-server-stack**

Run: `cd /Users/joeradford/dev/home-server-stack && make validate`
Expected: PASS

- [ ] **Step 4: Verify no stale vault references in renamed files**

Run: `cd /Users/joeradford/dev/bede && grep -rn '"vault"' bede-data/src/bede_data/ingest/ bede-data/src/bede_data/api/usage_data.py`
Expected: No output (the vault_queue references are expected in their own files)

Run: `cd /Users/joeradford/dev/bede && grep -rn '/api/vault/' bede-data-mcp/src/`
Expected: No output

Run: `cd /Users/joeradford/dev/bede && grep -rn '/ingest/vault' bede-data/src/ bede-data/tests/`
Expected: No output
