# Deal Monitoring & News Curation Implementation Plan

> **Status: COMPLETE** — All tasks done. Code tasks 1-7 merged in bede PR #73 (2026-05-07). Task 8: monitored items seeded, 46 dead URLs and 47 price history records migrated from price-checker-memory.md, vault preference files archived. Task 9: Deal Scout running Sundays 2pm AEST with 5 parallel steps (Groceries, Vacuum, Clothing, Camping Gear, Events). Task 10: News Digest running weekdays 7am AEST, `/digest` command merged.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deal monitoring (price tracking, restock alerts) and news curation (feed aggregation, digest delivery) to Bede, replacing the current vault-based preference files with SQLite-managed config and operational data.

**Architecture:** Both features follow Bede's existing pattern: Claude receives a scheduled task prompt, reads config from `monitored_items` via MCP tools, uses browser-mcp to scrape the web, and records results via new MCP tools backed by new bede-data API endpoints and SQLite tables. Telegram delivery uses the existing scheduler pipeline. The `monitored_items` table already exists with CRUD API and MCP tools — this plan adds the operational tables (`price_history`, `dead_urls`, `articles`) and the API/MCP surface to consume them.

**Tech Stack:** Python 3.14, FastAPI, SQLite, FastMCP, pytest, Playwright MCP (browser-mcp)

**Repo:** All code changes are in `/Users/joeradford/dev/bede`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `bede-data/src/bede_data/api/deals.py` | FastAPI router for price history and dead URL endpoints |
| `bede-data/src/bede_data/api/news.py` | FastAPI router for article storage and querying |
| `bede-data/tests/test_api_deals.py` | Tests for deals API |
| `bede-data/tests/test_api_news.py` | Tests for news API |
| `bede-data-mcp/tests/test_deals_tools.py` | Tests for deal MCP tools |
| `bede-data-mcp/tests/test_news_tools.py` | Tests for news MCP tools |

### Modified files

| File | Changes |
|------|---------|
| `bede-data/src/bede_data/db/schema.py` | Add `price_history`, `dead_urls`, `articles` tables; bump SCHEMA_VERSION to 9 |
| `bede-data/src/bede_data/app.py` | Mount deals and news routers |
| `bede-data/src/bede_data/api/config_api.py` | Add PUT endpoint for `monitored_items` update |
| `bede-data-mcp/src/bede_data_mcp/server.py` | Add deal monitoring and news curation MCP tools; add `update_monitored_item` tool |

---

## Part A: Deal Monitoring

### Task 1: Schema — add `price_history` and `dead_urls` tables

**Files:**
- Modify: `bede-data/src/bede_data/db/schema.py`
- Test: `bede-data/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Add to `bede-data/tests/test_db.py`:

```python
def test_price_history_table_exists(db):
    db.execute(
        "INSERT INTO price_history (monitored_item_id, url, price, currency, in_stock, checked_at) "
        "VALUES (1, 'https://example.com', 99.95, 'AUD', 1, '2026-05-07T00:00:00Z')"
    )
    row = db.execute("SELECT * FROM price_history WHERE id = 1").fetchone()
    assert row is not None
    assert row["price"] == 99.95


def test_dead_urls_table_exists(db):
    db.execute(
        "INSERT INTO dead_urls (url, category, last_error, checked_at) "
        "VALUES ('https://dead.example.com', 'deal', '404 Not Found', '2026-05-07T00:00:00Z')"
    )
    row = db.execute("SELECT * FROM dead_urls WHERE id = 1").fetchone()
    assert row is not None
    assert row["fail_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_db.py::test_price_history_table_exists tests/test_db.py::test_dead_urls_table_exists -v`
Expected: FAIL with "no such table: price_history"

- [ ] **Step 3: Add tables to schema**

In `bede-data/src/bede_data/db/schema.py`, change `SCHEMA_VERSION = 8` to `SCHEMA_VERSION = 9`.

Append to the `SCHEMA_SQL` string (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS price_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    monitored_item_id INTEGER NOT NULL REFERENCES monitored_items(id),
    url               TEXT NOT NULL,
    price             REAL,
    currency          TEXT NOT NULL DEFAULT 'AUD',
    in_stock          INTEGER,
    notes             TEXT,
    checked_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dead_urls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL UNIQUE,
    category     TEXT,
    fail_count   INTEGER NOT NULL DEFAULT 1,
    last_error   TEXT,
    first_seen   TEXT NOT NULL DEFAULT (datetime('now')),
    checked_at   TEXT NOT NULL DEFAULT (datetime('now')),
    disabled     INTEGER NOT NULL DEFAULT 0
);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_db.py::test_price_history_table_exists tests/test_db.py::test_dead_urls_table_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/db/schema.py bede-data/tests/test_db.py
git commit -m "feat: add price_history and dead_urls tables (schema v9)"
```

---

### Task 2: bede-data API — deals router

**Files:**
- Create: `bede-data/src/bede_data/api/deals.py`
- Modify: `bede-data/src/bede_data/app.py`
- Test: `bede-data/tests/test_api_deals.py`

- [ ] **Step 1: Write the failing tests**

Create `bede-data/tests/test_api_deals.py`:

```python
import json


def test_record_price_check(client):
    # Create a monitored item first
    item = client.post(
        "/api/config/monitored-items",
        json={"category": "deal", "name": "Camping Gear", "config": "{}"},
    ).json()

    response = client.post(
        "/api/deals/price-checks",
        json={
            "monitored_item_id": item["id"],
            "url": "https://anaconda.com.au/product/123",
            "price": 149.95,
            "currency": "AUD",
            "in_stock": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["price"] == 149.95
    assert data["in_stock"] is True


def test_record_price_check_out_of_stock(client):
    item = client.post(
        "/api/config/monitored-items",
        json={"category": "deal", "name": "Gear", "config": "{}"},
    ).json()

    response = client.post(
        "/api/deals/price-checks",
        json={
            "monitored_item_id": item["id"],
            "url": "https://example.com/product",
            "in_stock": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["price"] is None
    assert response.json()["in_stock"] is False


def test_get_price_history(client):
    item = client.post(
        "/api/config/monitored-items",
        json={"category": "deal", "name": "Gear", "config": "{}"},
    ).json()

    client.post(
        "/api/deals/price-checks",
        json={
            "monitored_item_id": item["id"],
            "url": "https://example.com/p",
            "price": 100.0,
            "in_stock": True,
        },
    )
    client.post(
        "/api/deals/price-checks",
        json={
            "monitored_item_id": item["id"],
            "url": "https://example.com/p",
            "price": 89.95,
            "in_stock": True,
        },
    )

    response = client.get(f"/api/deals/price-history/{item['id']}")
    assert response.status_code == 200
    checks = response.json()["checks"]
    assert len(checks) == 2
    assert checks[0]["price"] == 89.95  # most recent first


def test_get_price_history_with_limit(client):
    item = client.post(
        "/api/config/monitored-items",
        json={"category": "deal", "name": "Gear", "config": "{}"},
    ).json()

    for i in range(5):
        client.post(
            "/api/deals/price-checks",
            json={
                "monitored_item_id": item["id"],
                "url": "https://example.com/p",
                "price": 100.0 + i,
                "in_stock": True,
            },
        )

    response = client.get(f"/api/deals/price-history/{item['id']}", params={"limit": 3})
    assert len(response.json()["checks"]) == 3


def test_report_dead_url(client):
    response = client.post(
        "/api/deals/dead-urls",
        json={
            "url": "https://broken.example.com/product",
            "category": "deal",
            "last_error": "404 Not Found",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["fail_count"] == 1
    assert data["url"] == "https://broken.example.com/product"


def test_report_dead_url_increments_fail_count(client):
    for _ in range(3):
        client.post(
            "/api/deals/dead-urls",
            json={
                "url": "https://broken.example.com",
                "category": "deal",
                "last_error": "timeout",
            },
        )

    response = client.get("/api/deals/dead-urls")
    urls = response.json()["urls"]
    assert len(urls) == 1
    assert urls[0]["fail_count"] == 3


def test_list_dead_urls(client):
    client.post(
        "/api/deals/dead-urls",
        json={"url": "https://a.com", "category": "deal", "last_error": "404"},
    )
    client.post(
        "/api/deals/dead-urls",
        json={"url": "https://b.com", "category": "news", "last_error": "403"},
    )

    # All
    response = client.get("/api/deals/dead-urls")
    assert len(response.json()["urls"]) == 2

    # Filter by category
    response = client.get("/api/deals/dead-urls", params={"category": "deal"})
    assert len(response.json()["urls"]) == 1


def test_list_dead_urls_excludes_disabled(client):
    resp = client.post(
        "/api/deals/dead-urls",
        json={"url": "https://old.com", "category": "deal", "last_error": "gone"},
    )
    url_id = resp.json()["id"]

    client.put(f"/api/deals/dead-urls/{url_id}", json={"disabled": True})

    response = client.get("/api/deals/dead-urls")
    assert len(response.json()["urls"]) == 0


def test_update_dead_url(client):
    resp = client.post(
        "/api/deals/dead-urls",
        json={"url": "https://old.com", "category": "deal", "last_error": "404"},
    )
    url_id = resp.json()["id"]

    response = client.put(f"/api/deals/dead-urls/{url_id}", json={"disabled": True})
    assert response.status_code == 200
    assert response.json()["disabled"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_api_deals.py -v`
Expected: FAIL (module not found / 404)

- [ ] **Step 3: Write the deals router**

Create `bede-data/src/bede_data/api/deals.py`:

```python
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from bede_data.db.connection import get_db

router = APIRouter(prefix="/api/deals", tags=["deals"])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- Price checks ----


class PriceCheckCreate(BaseModel):
    monitored_item_id: int
    url: str
    price: float | None = None
    currency: str = "AUD"
    in_stock: bool | None = None
    notes: str | None = None


@router.post("/price-checks", status_code=201)
def record_price_check(
    body: PriceCheckCreate, conn: sqlite3.Connection = Depends(get_db)
):
    now = _now()
    cursor = conn.execute(
        "INSERT INTO price_history (monitored_item_id, url, price, currency, in_stock, notes, checked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            body.monitored_item_id,
            body.url,
            body.price,
            body.currency,
            int(body.in_stock) if body.in_stock is not None else None,
            body.notes,
            now,
        ),
    )
    conn.commit()
    return _get_price_check(conn, cursor.lastrowid)


@router.get("/price-history/{item_id}")
def get_price_history(
    item_id: int,
    limit: int = Query(50, ge=1, le=500),
    url: str | None = Query(None),
    conn: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT id, monitored_item_id, url, price, currency, in_stock, notes, checked_at FROM price_history WHERE monitored_item_id = ?"
    params: list = [item_id]
    if url:
        query += " AND url = ?"
        params.append(url)
    query += " ORDER BY checked_at DESC LIMIT ?"
    params.append(limit)
    cursor = conn.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        if r["in_stock"] is not None:
            r["in_stock"] = bool(r["in_stock"])
    return {"checks": rows}


def _get_price_check(conn: sqlite3.Connection, check_id: int) -> dict:
    cursor = conn.execute(
        "SELECT id, monitored_item_id, url, price, currency, in_stock, notes, checked_at FROM price_history WHERE id = ?",
        (check_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {}
    r = dict(row)
    if r["in_stock"] is not None:
        r["in_stock"] = bool(r["in_stock"])
    return r


# ---- Dead URLs ----


class DeadUrlReport(BaseModel):
    url: str
    category: str | None = None
    last_error: str | None = None


class DeadUrlUpdate(BaseModel):
    disabled: bool | None = None
    last_error: str | None = None


@router.post("/dead-urls", status_code=201)
def report_dead_url(body: DeadUrlReport, conn: sqlite3.Connection = Depends(get_db)):
    now = _now()
    existing = conn.execute(
        "SELECT id, fail_count FROM dead_urls WHERE url = ?", (body.url,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE dead_urls SET fail_count = fail_count + 1, last_error = ?, checked_at = ? WHERE id = ?",
            (body.last_error, now, existing["id"]),
        )
        conn.commit()
        return _get_dead_url(conn, existing["id"])

    cursor = conn.execute(
        "INSERT INTO dead_urls (url, category, last_error, first_seen, checked_at) VALUES (?, ?, ?, ?, ?)",
        (body.url, body.category, body.last_error, now, now),
    )
    conn.commit()
    return _get_dead_url(conn, cursor.lastrowid)


@router.get("/dead-urls")
def list_dead_urls(
    category: str | None = Query(None),
    conn: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT id, url, category, fail_count, last_error, first_seen, checked_at, disabled FROM dead_urls WHERE disabled = 0"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY checked_at DESC"
    cursor = conn.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        r["disabled"] = bool(r["disabled"])
    return {"urls": rows}


@router.put("/dead-urls/{url_id}")
def update_dead_url(
    url_id: int, body: DeadUrlUpdate, conn: sqlite3.Connection = Depends(get_db)
):
    existing = _get_dead_url(conn, url_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Dead URL not found")

    updates: dict = {"checked_at": _now()}
    if body.disabled is not None:
        updates["disabled"] = int(body.disabled)
    if body.last_error is not None:
        updates["last_error"] = body.last_error

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE dead_urls SET {set_clause} WHERE id = ?",
        [*updates.values(), url_id],
    )
    conn.commit()
    return _get_dead_url(conn, url_id)


def _get_dead_url(conn: sqlite3.Connection, url_id: int) -> dict:
    cursor = conn.execute(
        "SELECT id, url, category, fail_count, last_error, first_seen, checked_at, disabled FROM dead_urls WHERE id = ?",
        (url_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {}
    r = dict(row)
    r["disabled"] = bool(r["disabled"])
    return r
```

- [ ] **Step 4: Mount the deals router in app.py**

In `bede-data/src/bede_data/app.py`, add import:

```python
from bede_data.api.deals import router as deals_router
```

Add after `app.include_router(message_queue_router)`:

```python
    app.include_router(deals_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_api_deals.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/api/deals.py bede-data/src/bede_data/app.py bede-data/tests/test_api_deals.py
git commit -m "feat: add deals API for price history and dead URL tracking"
```

---

### Task 3: Add `update_monitored_item` endpoint

The existing `monitored_items` API has create, list, and delete but no update. Claude needs to modify item configs (add/remove products, change thresholds) via conversation.

**Files:**
- Modify: `bede-data/src/bede_data/api/config_api.py`
- Test: `bede-data/tests/test_api_config.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`
- Test: `bede-data-mcp/tests/test_config_tools.py`

- [ ] **Step 1: Write the failing tests (bede-data)**

Add to `bede-data/tests/test_api_config.py`:

```python
def test_update_monitored_item(client):
    resp = client.post(
        "/api/config/monitored-items",
        json={"category": "deal", "name": "Camping Gear", "config": '{"items": []}'},
    )
    item_id = resp.json()["id"]

    response = client.put(
        f"/api/config/monitored-items/{item_id}",
        json={"config": '{"items": ["tent"]}'},
    )
    assert response.status_code == 200
    assert json.loads(response.json()["config"]) == {"items": ["tent"]}
    assert response.json()["name"] == "Camping Gear"


def test_update_monitored_item_name(client):
    resp = client.post(
        "/api/config/monitored-items",
        json={"category": "deal", "name": "Old Name", "config": "{}"},
    )
    item_id = resp.json()["id"]

    response = client.put(
        f"/api/config/monitored-items/{item_id}",
        json={"name": "New Name"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_update_monitored_item_not_found(client):
    response = client.put(
        "/api/config/monitored-items/999",
        json={"name": "X"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_api_config.py::test_update_monitored_item tests/test_api_config.py::test_update_monitored_item_name tests/test_api_config.py::test_update_monitored_item_not_found -v`
Expected: FAIL (405 Method Not Allowed)

- [ ] **Step 3: Add update endpoint**

In `bede-data/src/bede_data/api/config_api.py`, add after the `delete_monitored_item` function:

```python
@router.put("/monitored-items/{item_id}")
def update_monitored_item(
    item_id: int, body: MonitoredItemUpdate, conn: sqlite3.Connection = Depends(get_db)
):
    existing = _get_monitored_item(conn, item_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Monitored item not found")

    updates: dict = {"updated_at": _now()}
    if body.name is not None:
        updates["name"] = body.name
    if body.config is not None:
        updates["config"] = body.config
    if body.enabled is not None:
        updates["enabled"] = int(body.enabled)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE monitored_items SET {set_clause} WHERE id = ?",
        [*updates.values(), item_id],
    )
    conn.commit()
    return _get_monitored_item(conn, item_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_api_config.py -v`
Expected: All PASS

- [ ] **Step 5: Write the failing MCP tool test**

Add to `bede-data-mcp/tests/test_config_tools.py`:

Import `update_monitored_item` at the top alongside the other imports.

```python
async def test_update_monitored_item(api):
    api.put.return_value = {
        "id": 1,
        "category": "deals",
        "name": "updated name",
        "config": '{"items": ["tent"]}',
    }
    result = await update_monitored_item(1, name="updated name", config='{"items": ["tent"]}')
    api.put.assert_called_once_with(
        "/api/config/monitored-items/1",
        {"name": "updated name", "config": '{"items": ["tent"]}'},
    )
    assert result["name"] == "updated name"


async def test_update_monitored_item_enabled(api):
    api.put.return_value = {"id": 1, "enabled": False}
    await update_monitored_item(1, enabled=False)
    api.put.assert_called_once_with(
        "/api/config/monitored-items/1", {"enabled": False}
    )
```

- [ ] **Step 6: Run MCP tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest tests/test_config_tools.py::test_update_monitored_item tests/test_config_tools.py::test_update_monitored_item_enabled -v`
Expected: FAIL (ImportError)

- [ ] **Step 7: Add the MCP tool**

In `bede-data-mcp/src/bede_data_mcp/server.py`, add after `delete_monitored_item`:

```python
@mcp.tool()
async def update_monitored_item(
    item_id: int,
    name: str | None = None,
    config: str | None = None,
    enabled: bool | None = None,
) -> dict:
    """Update a monitored item's name, config, or enabled status.

    Args:
        item_id: ID of the item to update.
        name: New human-readable name.
        config: New JSON config string.
        enabled: Set enabled/disabled.
    """
    body: dict = {}
    if name is not None:
        body["name"] = name
    if config is not None:
        body["config"] = config
    if enabled is not None:
        body["enabled"] = enabled
    return await client.put(f"/api/config/monitored-items/{item_id}", body)
```

- [ ] **Step 8: Run all MCP config tests**

Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest tests/test_config_tools.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/api/config_api.py bede-data/tests/test_api_config.py bede-data-mcp/src/bede_data_mcp/server.py bede-data-mcp/tests/test_config_tools.py
git commit -m "feat: add update endpoint for monitored items"
```

---

### Task 4: bede-data-mcp — deal monitoring MCP tools

**Files:**
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`
- Create: `bede-data-mcp/tests/test_deals_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `bede-data-mcp/tests/test_deals_tools.py`:

```python
from bede_data_mcp.server import (
    get_price_history,
    list_dead_urls,
    record_price_check,
    report_dead_url,
    update_dead_url,
)


async def test_record_price_check(api):
    api.post.return_value = {
        "id": 1,
        "monitored_item_id": 5,
        "url": "https://example.com/p",
        "price": 149.95,
        "in_stock": True,
    }
    result = await record_price_check(5, "https://example.com/p", 149.95, "AUD", True)
    api.post.assert_called_once_with(
        "/api/deals/price-checks",
        {
            "monitored_item_id": 5,
            "url": "https://example.com/p",
            "price": 149.95,
            "currency": "AUD",
            "in_stock": True,
        },
    )
    assert result["price"] == 149.95


async def test_record_price_check_out_of_stock(api):
    api.post.return_value = {"id": 2, "price": None, "in_stock": False}
    result = await record_price_check(5, "https://example.com/p", in_stock=False)
    api.post.assert_called_once_with(
        "/api/deals/price-checks",
        {
            "monitored_item_id": 5,
            "url": "https://example.com/p",
            "in_stock": False,
        },
    )
    assert result["in_stock"] is False


async def test_record_price_check_with_notes(api):
    api.post.return_value = {"id": 3}
    await record_price_check(5, "https://example.com/p", price=99.0, notes="sale ends Friday")
    call_body = api.post.call_args[0][1]
    assert call_body["notes"] == "sale ends Friday"


async def test_get_price_history(api):
    api.get.return_value = {
        "checks": [
            {"id": 2, "price": 89.95, "checked_at": "2026-05-07T12:00:00Z"},
            {"id": 1, "price": 99.95, "checked_at": "2026-05-06T12:00:00Z"},
        ]
    }
    result = await get_price_history(5)
    api.get.assert_called_once_with("/api/deals/price-history/5")
    assert len(result["checks"]) == 2


async def test_get_price_history_with_limit(api):
    api.get.return_value = {"checks": []}
    await get_price_history(5, limit=10)
    api.get.assert_called_once_with("/api/deals/price-history/5", limit=10)


async def test_get_price_history_with_url_filter(api):
    api.get.return_value = {"checks": []}
    await get_price_history(5, url="https://example.com/p")
    api.get.assert_called_once_with("/api/deals/price-history/5", url="https://example.com/p")


async def test_report_dead_url(api):
    api.post.return_value = {
        "id": 1,
        "url": "https://dead.com",
        "fail_count": 1,
    }
    result = await report_dead_url("https://dead.com", "deal", "404 Not Found")
    api.post.assert_called_once_with(
        "/api/deals/dead-urls",
        {"url": "https://dead.com", "category": "deal", "last_error": "404 Not Found"},
    )
    assert result["fail_count"] == 1


async def test_list_dead_urls(api):
    api.get.return_value = {"urls": [{"id": 1, "url": "https://dead.com"}]}
    result = await list_dead_urls()
    api.get.assert_called_once_with("/api/deals/dead-urls")
    assert len(result["urls"]) == 1


async def test_list_dead_urls_by_category(api):
    api.get.return_value = {"urls": []}
    await list_dead_urls(category="deal")
    api.get.assert_called_once_with("/api/deals/dead-urls", category="deal")


async def test_update_dead_url(api):
    api.put.return_value = {"id": 1, "disabled": True}
    result = await update_dead_url(1, disabled=True)
    api.put.assert_called_once_with("/api/deals/dead-urls/1", {"disabled": True})
    assert result["disabled"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest tests/test_deals_tools.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Add deal MCP tools**

In `bede-data-mcp/src/bede_data_mcp/server.py`, add a new section after the monitored items tools:

```python
# ---------------------------------------------------------------------------
# Deal monitoring tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def record_price_check(
    monitored_item_id: int,
    url: str,
    price: float | None = None,
    currency: str = "AUD",
    in_stock: bool | None = None,
    notes: str | None = None,
) -> dict:
    """Record a price check observation after scraping a retailer page.

    Call this after visiting a product URL to persist the price and stock status.
    The system tracks history so price drops and restocks can be detected.

    Args:
        monitored_item_id: ID of the monitored item this check belongs to.
        url: The product page URL that was checked.
        price: The observed price (omit if product page doesn't show a price).
        currency: Currency code (default AUD).
        in_stock: Whether the product is currently in stock.
        notes: Optional notes (e.g. 'sale ends Friday', 'clearance').
    """
    body: dict = {"monitored_item_id": monitored_item_id, "url": url}
    if price is not None:
        body["price"] = price
    if currency != "AUD":
        body["currency"] = currency
    if in_stock is not None:
        body["in_stock"] = in_stock
    if notes is not None:
        body["notes"] = notes
    return await client.post("/api/deals/price-checks", body)


@mcp.tool()
async def get_price_history(
    monitored_item_id: int,
    limit: int | None = None,
    url: str | None = None,
) -> dict:
    """Get price check history for a monitored item.

    Returns checks in reverse chronological order. Compare the most recent
    check against previous ones to detect price drops or restocks.

    Args:
        monitored_item_id: ID of the monitored item.
        limit: Max number of checks to return (default 50).
        url: Filter to a specific product URL.
    """
    kwargs: dict = {}
    if limit is not None:
        kwargs["limit"] = limit
    if url is not None:
        kwargs["url"] = url
    return await client.get(f"/api/deals/price-history/{monitored_item_id}", **kwargs)


@mcp.tool()
async def report_dead_url(url: str, category: str | None = None, error: str | None = None) -> dict:
    """Report a URL that failed to load or returned an error.

    Call this when a product page returns 404, 403, redirects to a homepage,
    or otherwise fails. The system tracks failure counts — URLs with repeated
    failures can be skipped in future checks.

    Args:
        url: The URL that failed.
        category: Category for grouping (e.g. 'deal', 'news').
        error: Description of the failure (e.g. '404 Not Found', 'redirect to homepage').
    """
    body: dict = {"url": url}
    if category is not None:
        body["category"] = category
    if error is not None:
        body["last_error"] = error
    return await client.post("/api/deals/dead-urls", body)


@mcp.tool()
async def list_dead_urls(category: str | None = None) -> dict:
    """List known dead URLs to skip during scraping.

    Check this before attempting to scrape — URLs in this list have
    previously failed and may waste time.

    Args:
        category: Filter by category (e.g. 'deal', 'news').
    """
    kwargs: dict = {}
    if category is not None:
        kwargs["category"] = category
    return await client.get("/api/deals/dead-urls", **kwargs)


@mcp.tool()
async def update_dead_url(
    url_id: int,
    disabled: bool | None = None,
    last_error: str | None = None,
) -> dict:
    """Update a dead URL entry (e.g. to disable it permanently).

    Args:
        url_id: ID of the dead URL entry.
        disabled: Set to true to permanently skip this URL.
        last_error: Update the error description.
    """
    body: dict = {}
    if disabled is not None:
        body["disabled"] = disabled
    if last_error is not None:
        body["last_error"] = last_error
    return await client.put(f"/api/deals/dead-urls/{url_id}", body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest tests/test_deals_tools.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suites for both services**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest -v`
Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/src/bede_data_mcp/server.py bede-data-mcp/tests/test_deals_tools.py
git commit -m "feat: add deal monitoring MCP tools (price checks, dead URLs)"
```

---

## Part B: News Curation

### Task 5: Schema — add `articles` table

**Files:**
- Modify: `bede-data/src/bede_data/db/schema.py` (already modified in Task 1 — add to same edit)
- Test: `bede-data/tests/test_db.py`

> **Note:** If Task 1 is already committed, this task adds the `articles` table as a separate schema addition. The SCHEMA_VERSION stays at 9 (set in Task 1) since CREATE TABLE IF NOT EXISTS is idempotent.

- [ ] **Step 1: Write the failing test**

Add to `bede-data/tests/test_db.py`:

```python
def test_articles_table_exists(db):
    db.execute(
        "INSERT INTO articles (url, title, source_name, category, summary, fetched_at) "
        "VALUES ('https://example.com/article', 'Test Article', 'Hacker News', 'tech', 'Summary text', '2026-05-07T00:00:00Z')"
    )
    row = db.execute("SELECT * FROM articles WHERE id = 1").fetchone()
    assert row is not None
    assert row["title"] == "Test Article"


def test_articles_url_unique(db):
    db.execute(
        "INSERT INTO articles (url, title, source_name, category, fetched_at) "
        "VALUES ('https://example.com/a', 'First', 'src', 'tech', '2026-05-07T00:00:00Z')"
    )
    import sqlite3 as _sqlite3
    try:
        db.execute(
            "INSERT INTO articles (url, title, source_name, category, fetched_at) "
            "VALUES ('https://example.com/a', 'Duplicate', 'src', 'tech', '2026-05-07T01:00:00Z')"
        )
        assert False, "Should have raised IntegrityError"
    except _sqlite3.IntegrityError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_db.py::test_articles_table_exists tests/test_db.py::test_articles_url_unique -v`
Expected: FAIL with "no such table: articles"

- [ ] **Step 3: Add the articles table to schema**

In `bede-data/src/bede_data/db/schema.py`, append to `SCHEMA_SQL` (before closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS articles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    category         TEXT,
    summary          TEXT,
    fetched_at       TEXT NOT NULL DEFAULT (datetime('now')),
    digest_date      TEXT
);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_db.py::test_articles_table_exists tests/test_db.py::test_articles_url_unique -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/db/schema.py bede-data/tests/test_db.py
git commit -m "feat: add articles table for news curation"
```

---

### Task 6: bede-data API — news router

**Files:**
- Create: `bede-data/src/bede_data/api/news.py`
- Modify: `bede-data/src/bede_data/app.py`
- Create: `bede-data/tests/test_api_news.py`

- [ ] **Step 1: Write the failing tests**

Create `bede-data/tests/test_api_news.py`:

```python
def test_save_article(client):
    response = client.post(
        "/api/news/articles",
        json={
            "url": "https://example.com/article-1",
            "title": "AI Breakthrough",
            "source_name": "Hacker News",
            "category": "ai",
            "summary": "Researchers achieved...",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "AI Breakthrough"
    assert data["digest_date"] is None


def test_save_article_duplicate_returns_existing(client):
    client.post(
        "/api/news/articles",
        json={
            "url": "https://example.com/dupe",
            "title": "Original",
            "source_name": "HN",
            "category": "tech",
        },
    )
    response = client.post(
        "/api/news/articles",
        json={
            "url": "https://example.com/dupe",
            "title": "Duplicate Attempt",
            "source_name": "HN",
            "category": "tech",
        },
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Original"
    assert response.json()["already_existed"] is True


def test_list_articles(client):
    client.post(
        "/api/news/articles",
        json={"url": "https://a.com", "title": "A", "source_name": "HN", "category": "tech"},
    )
    client.post(
        "/api/news/articles",
        json={"url": "https://b.com", "title": "B", "source_name": "HN", "category": "ai"},
    )

    response = client.get("/api/news/articles")
    assert len(response.json()["articles"]) == 2


def test_list_articles_filter_category(client):
    client.post(
        "/api/news/articles",
        json={"url": "https://a.com", "title": "A", "source_name": "HN", "category": "tech"},
    )
    client.post(
        "/api/news/articles",
        json={"url": "https://b.com", "title": "B", "source_name": "HN", "category": "ai"},
    )

    response = client.get("/api/news/articles", params={"category": "ai"})
    articles = response.json()["articles"]
    assert len(articles) == 1
    assert articles[0]["category"] == "ai"


def test_list_articles_unsent_only(client):
    client.post(
        "/api/news/articles",
        json={"url": "https://a.com", "title": "A", "source_name": "HN", "category": "tech"},
    )
    resp = client.post(
        "/api/news/articles",
        json={"url": "https://b.com", "title": "B", "source_name": "HN", "category": "tech"},
    )
    article_id = resp.json()["id"]
    client.put(
        f"/api/news/articles/{article_id}/digest",
        json={"digest_date": "2026-05-07"},
    )

    response = client.get("/api/news/articles", params={"unsent": "true"})
    articles = response.json()["articles"]
    assert len(articles) == 1
    assert articles[0]["url"] == "https://a.com"


def test_mark_article_in_digest(client):
    resp = client.post(
        "/api/news/articles",
        json={"url": "https://a.com", "title": "A", "source_name": "HN", "category": "tech"},
    )
    article_id = resp.json()["id"]

    response = client.put(
        f"/api/news/articles/{article_id}/digest",
        json={"digest_date": "2026-05-07"},
    )
    assert response.status_code == 200
    assert response.json()["digest_date"] == "2026-05-07"


def test_check_article_exists(client):
    response = client.get(
        "/api/news/articles/exists",
        params={"url": "https://nonexistent.com"},
    )
    assert response.json()["exists"] is False

    client.post(
        "/api/news/articles",
        json={"url": "https://exists.com", "title": "X", "source_name": "HN", "category": "tech"},
    )
    response = client.get(
        "/api/news/articles/exists",
        params={"url": "https://exists.com"},
    )
    assert response.json()["exists"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_api_news.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Write the news router**

Create `bede-data/src/bede_data/api/news.py`:

```python
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from bede_data.db.connection import get_db

router = APIRouter(prefix="/api/news", tags=["news"])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ArticleCreate(BaseModel):
    url: str
    title: str
    source_name: str
    category: str | None = None
    summary: str | None = None


class DigestMark(BaseModel):
    digest_date: str


@router.post("/articles", status_code=201)
def save_article(body: ArticleCreate, conn: sqlite3.Connection = Depends(get_db)):
    existing = conn.execute(
        "SELECT id, url, title, source_name, category, summary, fetched_at, digest_date FROM articles WHERE url = ?",
        (body.url,),
    ).fetchone()
    if existing:
        r = dict(existing)
        r["already_existed"] = True
        return r

    now = _now()
    cursor = conn.execute(
        "INSERT INTO articles (url, title, source_name, category, summary, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        (body.url, body.title, body.source_name, body.category, body.summary, now),
    )
    conn.commit()
    return _get_article(conn, cursor.lastrowid)


@router.get("/articles")
def list_articles(
    category: str | None = Query(None),
    source_name: str | None = Query(None),
    unsent: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    conn: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT id, url, title, source_name, category, summary, fetched_at, digest_date FROM articles WHERE 1=1"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if source_name:
        query += " AND source_name = ?"
        params.append(source_name)
    if unsent:
        query += " AND digest_date IS NULL"
    query += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)
    cursor = conn.execute(query, params)
    return {"articles": [dict(r) for r in cursor.fetchall()]}


@router.get("/articles/exists")
def check_article_exists(
    url: str = Query(...), conn: sqlite3.Connection = Depends(get_db)
):
    row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
    return {"exists": row is not None, "url": url}


@router.put("/articles/{article_id}/digest")
def mark_article_in_digest(
    article_id: int, body: DigestMark, conn: sqlite3.Connection = Depends(get_db)
):
    existing = _get_article(conn, article_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Article not found")
    conn.execute(
        "UPDATE articles SET digest_date = ? WHERE id = ?",
        (body.digest_date, article_id),
    )
    conn.commit()
    return _get_article(conn, article_id)


def _get_article(conn: sqlite3.Connection, article_id: int) -> dict:
    cursor = conn.execute(
        "SELECT id, url, title, source_name, category, summary, fetched_at, digest_date FROM articles WHERE id = ?",
        (article_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {}
    return dict(row)
```

- [ ] **Step 4: Mount the news router in app.py**

In `bede-data/src/bede_data/app.py`, add import:

```python
from bede_data.api.news import router as news_router
```

Add after `app.include_router(deals_router)`:

```python
    app.include_router(news_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest tests/test_api_news.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data/src/bede_data/api/news.py bede-data/src/bede_data/app.py bede-data/tests/test_api_news.py
git commit -m "feat: add news API for article storage and digest tracking"
```

---

### Task 7: bede-data-mcp — news curation MCP tools

**Files:**
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`
- Create: `bede-data-mcp/tests/test_news_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `bede-data-mcp/tests/test_news_tools.py`:

```python
from bede_data_mcp.server import (
    check_article_exists,
    list_articles,
    mark_article_in_digest,
    save_article,
)


async def test_save_article(api):
    api.post.return_value = {
        "id": 1,
        "url": "https://example.com/article",
        "title": "AI News",
        "source_name": "TLDR AI",
        "category": "ai",
    }
    result = await save_article(
        "https://example.com/article", "AI News", "TLDR AI", category="ai", summary="Big things."
    )
    api.post.assert_called_once_with(
        "/api/news/articles",
        {
            "url": "https://example.com/article",
            "title": "AI News",
            "source_name": "TLDR AI",
            "category": "ai",
            "summary": "Big things.",
        },
    )
    assert result["id"] == 1


async def test_save_article_minimal(api):
    api.post.return_value = {"id": 2}
    await save_article("https://example.com/a", "Title", "Source")
    api.post.assert_called_once_with(
        "/api/news/articles",
        {"url": "https://example.com/a", "title": "Title", "source_name": "Source"},
    )


async def test_list_articles(api):
    api.get.return_value = {"articles": [{"id": 1, "title": "A"}]}
    result = await list_articles()
    api.get.assert_called_once_with("/api/news/articles")
    assert len(result["articles"]) == 1


async def test_list_articles_filtered(api):
    api.get.return_value = {"articles": []}
    await list_articles(category="ai", unsent=True)
    api.get.assert_called_once_with("/api/news/articles", category="ai", unsent=True)


async def test_list_articles_by_source(api):
    api.get.return_value = {"articles": []}
    await list_articles(source_name="Hacker News")
    api.get.assert_called_once_with("/api/news/articles", source_name="Hacker News")


async def test_check_article_exists(api):
    api.get.return_value = {"exists": True, "url": "https://example.com"}
    result = await check_article_exists("https://example.com")
    api.get.assert_called_once_with("/api/news/articles/exists", url="https://example.com")
    assert result["exists"] is True


async def test_mark_article_in_digest(api):
    api.put.return_value = {"id": 1, "digest_date": "2026-05-07"}
    result = await mark_article_in_digest(1, "2026-05-07")
    api.put.assert_called_once_with(
        "/api/news/articles/1/digest", {"digest_date": "2026-05-07"}
    )
    assert result["digest_date"] == "2026-05-07"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest tests/test_news_tools.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Add news curation MCP tools**

In `bede-data-mcp/src/bede_data_mcp/server.py`, add a new section:

```python
# ---------------------------------------------------------------------------
# News curation tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def save_article(
    url: str,
    title: str,
    source_name: str,
    category: str | None = None,
    summary: str | None = None,
) -> dict:
    """Save an article found during news curation.

    Handles deduplication by URL — if the article already exists, returns
    the existing record with already_existed=true instead of creating a
    duplicate.

    Args:
        url: The article URL (used as dedup key).
        title: Article headline.
        source_name: Where it was found (e.g. 'Hacker News', 'TLDR AI').
        category: Topic category (e.g. 'ai', 'public_sector', 'platform_tech').
        summary: Brief summary of the article content.
    """
    body: dict = {"url": url, "title": title, "source_name": source_name}
    if category is not None:
        body["category"] = category
    if summary is not None:
        body["summary"] = summary
    return await client.post("/api/news/articles", body)


@mcp.tool()
async def list_articles(
    category: str | None = None,
    source_name: str | None = None,
    unsent: bool | None = None,
    limit: int | None = None,
) -> dict:
    """List saved articles, optionally filtered.

    Use unsent=true to get articles not yet included in any digest — this
    is the primary query for building a news digest.

    Args:
        category: Filter by topic category.
        source_name: Filter by source name.
        unsent: If true, only return articles not yet in a digest.
        limit: Max articles to return (default 50).
    """
    kwargs: dict = {}
    if category is not None:
        kwargs["category"] = category
    if source_name is not None:
        kwargs["source_name"] = source_name
    if unsent is not None:
        kwargs["unsent"] = unsent
    if limit is not None:
        kwargs["limit"] = limit
    return await client.get("/api/news/articles", **kwargs)


@mcp.tool()
async def check_article_exists(url: str) -> dict:
    """Check if an article URL has already been saved (deduplication check).

    Args:
        url: The article URL to check.
    """
    return await client.get("/api/news/articles/exists", url=url)


@mcp.tool()
async def mark_article_in_digest(article_id: int, digest_date: str) -> dict:
    """Mark an article as included in a digest.

    Call this after including an article in a news digest delivery so it
    won't appear in future unsent queries.

    Args:
        article_id: ID of the article.
        digest_date: The date of the digest (YYYY-MM-DD format).
    """
    return await client.put(
        f"/api/news/articles/{article_id}/digest",
        {"digest_date": digest_date},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest tests/test_news_tools.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suites for both services**

Run: `cd /Users/joeradford/dev/bede/bede-data && python -m pytest -v`
Run: `cd /Users/joeradford/dev/bede/bede-data-mcp && python -m pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/src/bede_data_mcp/server.py bede-data-mcp/tests/test_news_tools.py
git commit -m "feat: add news curation MCP tools (articles, digest tracking)"
```

---

## Part C: Vault Data Migration

### Task 8: Seed monitored_items from vault files

This is a one-time data load — not code. Once the infrastructure from Tasks 1-7 is deployed, seed the `monitored_items` table with data extracted from the vault preference files. This can be done via Claude conversation using the existing `create_monitored_item` MCP tool.

**No code changes needed.** This task documents the config JSON schemas and the data to load.

- [ ] **Step 1: Define config JSON schemas**

Each `monitored_item` row uses the `config` JSON column. Define consistent schemas per category:

**Deal items** (category=`"deal"`):

```json
{
  "items": [
    {
      "name": "SEBO X7 Boost",
      "target_price": 1000,
      "sizes": null,
      "urls": [
        "https://retailer1.com/product/sebo-x7",
        "https://retailer2.com/product/sebo-x7"
      ]
    }
  ],
  "retailers": [
    {"name": "Godfreys", "url": "https://godfreys.com.au", "clearance_url": null}
  ],
  "thresholds": {
    "min_discount_pct": 20,
    "report_any_discount": false,
    "budget": 2000,
    "notes": "Combined budget for corded + robot"
  },
  "search_hints": [
    "Check StaticICE for price comparison",
    "OzBargain tags: sebo, dreame"
  ]
}
```

**Event items** (category=`"event"`):

```json
{
  "artists": [
    {"name": "Four Tet", "genre": "electronic"},
    {"name": "Radiohead", "genre": "rock"}
  ],
  "venues": [
    {"name": "Sydney Opera House", "url": "https://www.sydneyoperahouse.com/whats-on"},
    {"name": "Ticketek", "url": "https://premier.ticketek.com.au"}
  ],
  "thresholds": {
    "max_results": 5,
    "lookahead_months": 3,
    "notes": "Quality over quantity, 3-5 strong matches per category"
  }
}
```

**News sources** (category=`"news"`):

```json
{
  "sources": [
    {"name": "TLDR AI", "url": "https://tldr.tech/ai", "topic": "ai"},
    {"name": "Platformer", "url": "https://www.platformer.news", "topic": "platform_tech"}
  ],
  "preferences": {
    "signal_over_firehose": true,
    "max_articles_per_source": 5
  }
}
```

- [ ] **Step 2: Load data via conversation**

After deploying the code from Tasks 1-7, use Bede (or Claude directly) to read each vault file and create the corresponding `monitored_item` entries via the `create_monitored_item` MCP tool. The vault files to process:

| Vault file | monitored_item name | category |
|-----------|---------------------|----------|
| `camping-gear.md` | Camping Gear | deal |
| `clothing-preferences.md` | Clothing | deal |
| `vacuum-preferences.md` | Vacuum | deal |
| `staples.md` | Grocery Staples | deal |
| `event-preferences.md` | Events | event |
| `digest-sources.md` | News Sources | news |

- [ ] **Step 3: Load operational history from price-checker-memory.md**

The `price-checker-memory.md` file contains historical data that should be loaded into:
- `dead_urls` table: 52 dead URL entries with dates and error reasons
- `price_history` table: Price trend data with dates, prices, stock status

This can be done as a prompted conversation task — ask Claude to read the vault file and call the appropriate MCP tools to persist each entry.

- [ ] **Step 4: Verify data loaded correctly**

Use the MCP tools to verify:
- `list_monitored_items(category="deal")` — should return 4 items
- `list_monitored_items(category="event")` — should return 1 item
- `list_monitored_items(category="news")` — should return 1 item
- `list_dead_urls()` — should return ~52 entries
- `get_price_history(item_id)` — should have historical entries

- [ ] **Step 5: Archive superseded vault files**

Once data is confirmed in SQLite, the following vault files are superseded and can be archived (moved to a `Bede/archived/` folder or deleted):
- `scout-rules.md`
- `price-checker-memory.md`
- `camping-gear.md`
- `clothing-preferences.md`
- `vacuum-preferences.md`
- `staples.md`
- `event-preferences.md`
- `digest-sources.md`

---

## Part D: Scheduled Task Configuration

### Task 9: Configure Deal Scout scheduled task

The "Deal Scout" task already exists as a schedule entry (the `/scout` command triggers "Deal Scout" in `main.py:194`). This task updates its prompt and config to use the new MCP tools and browser-mcp.

**No code changes needed.** This is task configuration via the schedules API.

- [ ] **Step 1: Design the task prompt**

The Deal Scout prompt should instruct Claude to:
1. Call `list_monitored_items(category="deal")` to get all deal categories
2. Call `list_dead_urls(category="deal")` to get URLs to skip
3. For each category, iterate through items and URLs
4. Use browser-mcp (`browser_navigate`, `browser_snapshot`) to visit each URL
5. Extract price and stock status from the page
6. Call `record_price_check(...)` for each observation
7. Call `get_price_history(...)` to compare against previous checks
8. Call `report_dead_url(...)` for any URLs that fail
9. Compile a summary of actionable findings (price drops, restocks, new deals)
10. Format the summary for Telegram delivery

Also load event items: `list_monitored_items(category="event")` and check venue pages for upcoming shows matching the artist watchlist.

- [ ] **Step 2: Configure multi-step task**

The Deal Scout should be a multi-step task with one step per monitored category (parallel execution). Update the schedule via the API:

```json
{
  "task_name": "Deal Scout",
  "cron_expression": "0 14 * * 0",
  "prompt": "You are running a deal and event scout. Check each category for price changes, restocks, and upcoming events. Report only actionable findings — price drops, items coming back in stock, events with artists on the watchlist. Skip dead URLs.",
  "model": "claude-sonnet-4-6",
  "timeout_seconds": 600,
  "task_config": {
    "steps": [
      {
        "name": "Deals",
        "prompt": "Check deal-category monitored items. For each item: 1) list_monitored_items(category='deal'), 2) list_dead_urls(category='deal') to know what to skip, 3) For each item's URLs, use browser to check the page, 4) record_price_check with observed price/stock, 5) get_price_history to detect changes. Report price drops, restocks, and new lows."
      },
      {
        "name": "Events",
        "prompt": "Check event-category monitored items. list_monitored_items(category='event') to get artist watchlist and venue sources. Visit venue pages via browser, search for matching artists. Report any upcoming shows for watchlisted artists with dates, venues, and ticket links."
      }
    ],
    "parallel": true
  }
}
```

- [ ] **Step 3: Verify task appears in scheduler**

After updating via API, wait up to 5 minutes for the scheduler reload, then verify the task runs correctly by triggering `/scout` via Telegram.

---

### Task 10: Configure News Digest scheduled task

**No code changes needed.** This is task configuration via the schedules API.

- [ ] **Step 1: Create the News Digest schedule**

```json
{
  "task_name": "News Digest",
  "cron_expression": "0 7 * * 1-5",
  "prompt": "You are curating a news digest. 1) list_monitored_items(category='news') to get sources, 2) For each source, use browser to visit the URL, 3) Identify the most relevant/interesting articles (signal, not firehose), 4) For each article: check_article_exists first, then save_article if new, 5) list_articles(unsent=true) to compile today's digest, 6) Format a concise digest grouped by topic, 7) mark_article_in_digest for each included article. Quality over quantity — aim for 5-10 total articles across all sources.",
  "model": "claude-sonnet-4-6",
  "timeout_seconds": 600
}
```

- [ ] **Step 2: Add `/digest` command handler to main.py**

This is the only code change in this task — add a manual trigger command.

In `bede-core/src/bede_core/main.py`, add after the `/triage` handler block:

```python
    app.add_handler(
        CommandHandler(
            "digest",
            create_task_trigger_handler(
                "News Digest", runner, data_client, settings.allowed_user_id
            ),
        )
    )
```

- [ ] **Step 3: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-core/src/bede_core/main.py
git commit -m "feat: add /digest command for manual news digest trigger"
```

- [ ] **Step 4: Verify task runs**

After deploying, trigger `/digest` via Telegram and verify the full flow works.

---

## Summary of Changes

| Service | Files Changed | What |
|---------|--------------|------|
| bede-data | `db/schema.py` | 3 new tables (price_history, dead_urls, articles), schema v9 |
| bede-data | `api/deals.py` (new) | Price check + dead URL endpoints |
| bede-data | `api/news.py` (new) | Article storage + digest tracking endpoints |
| bede-data | `api/config_api.py` | Update endpoint for monitored_items |
| bede-data | `app.py` | Mount deals + news routers |
| bede-data-mcp | `server.py` | 11 new MCP tools (5 deals, 4 news, 1 config update, 1 dead URL update) |
| bede-core | `main.py` | `/digest` command handler |
| bede-data | 3 new test files | Tests for deals API, news API, schema |
| bede-data-mcp | 2 new test files | Tests for deals + news MCP tools |

**MCP Tool Summary (new):**

| Tool | Purpose |
|------|---------|
| `update_monitored_item` | Update item name/config/enabled |
| `record_price_check` | Save price + stock observation |
| `get_price_history` | Query price history for comparison |
| `report_dead_url` | Report a failing URL |
| `list_dead_urls` | Get URLs to skip |
| `update_dead_url` | Disable a dead URL permanently |
| `save_article` | Save a curated article (dedup by URL) |
| `list_articles` | Query articles (filter by category, unsent) |
| `check_article_exists` | Dedup check before saving |
| `mark_article_in_digest` | Mark article as delivered |
