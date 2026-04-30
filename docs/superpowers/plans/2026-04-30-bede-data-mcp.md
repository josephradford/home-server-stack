# bede-data-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin MCP proxy server that forwards tool calls to bede-data's HTTP API, enabling Claude inside bede-core to discover and call personal data tools.

**Architecture:** FastMCP server with streamable-http transport. Each MCP tool is a thin async function that calls bede-data's REST API via httpx and returns the JSON response. No business logic, no direct database access — pure schema definition and HTTP forwarding. Error handling in the HTTP client returns structured error dicts so Claude can interpret failures gracefully.

**Tech Stack:** Python 3.12, FastMCP, httpx, pydantic-settings, pytest, uv

**Repository:** Code lives in `josephradford/bede` under `bede-data-mcp/`. This plan document lives in `josephradford/home-server-stack`. Docker Compose integration modifies `home-server-stack/docker-compose.ai.yml`.

**Specs:** [Design doc Section 2.4](../specs/2026-04-29-bede-design.md)

---

## File Structure

```
bede-data-mcp/
├── pyproject.toml
├── Dockerfile
├── src/
│   └── bede_data_mcp/
│       ├── __init__.py
│       ├── config.py              # Settings: BEDE_DATA_URL env var
│       ├── client.py              # HTTP helpers: get, post, put, delete with error handling
│       └── server.py              # All 42 MCP tool definitions + entrypoint
└── tests/
    ├── __init__.py
    ├── conftest.py                # Shared fixture: mocks client.get/post/put/delete
    ├── test_client.py             # HTTP client error handling
    ├── test_health_tools.py       # 6 health read tools
    ├── test_vault_tools.py        # 6 vault data read tools
    ├── test_location_tools.py     # 2 location + 2 weather read tools
    ├── test_memory_tools.py       # 5 memory CRUD tools
    ├── test_goal_tools.py         # 4 goal CRUD tools
    ├── test_analytics_tools.py    # 2 analytics tools
    ├── test_config_tools.py       # 9 config management tools
    └── test_misc_tools.py         # 6 misc tools (freshness, storage, conversations, tasks, vault queue)
```

All tool definitions live in `server.py`. Each tool is 4-8 lines (decorator, docstring, one HTTP call). The file is ~350 lines — repetitive but simple, matching the prototype `data-mcp/server.py` pattern.

---

## Tool Inventory

42 MCP tools mapped to bede-data HTTP endpoints. Parameter name differences between MCP and HTTP are noted.

| MCP Tool | HTTP Endpoint | Notes |
|----------|--------------|-------|
| **Health (6)** | | |
| `get_sleep(date, timezone)` | `GET /api/health/sleep` | |
| `get_activity(date, timezone)` | `GET /api/health/activity` | |
| `get_workouts(date, timezone)` | `GET /api/health/workouts` | |
| `get_heart_rate(date, timezone)` | `GET /api/health/heart-rate` | |
| `get_wellbeing(date, timezone)` | `GET /api/health/wellbeing` | |
| `get_medications(date, timezone)` | `GET /api/health/medications` | |
| **Vault Data (6)** | | |
| `get_screen_time(date, device?, top_n?, timezone)` | `GET /api/vault/screen-time` | |
| `get_safari_history(date, device?, domain_filter?, top_n?, timezone)` | `GET /api/vault/safari` | MCP `domain_filter` maps to HTTP `domain` |
| `get_youtube_history(date, timezone)` | `GET /api/vault/youtube` | |
| `get_podcasts(date, timezone)` | `GET /api/vault/podcasts` | |
| `get_claude_sessions(date, timezone)` | `GET /api/vault/claude-sessions` | |
| `get_bede_sessions(date, timezone)` | `GET /api/vault/bede-sessions` | |
| **Location (2)** | | |
| `get_location_summary(date, timezone)` | `GET /api/location/summary` | MCP `timezone` maps to HTTP `tz` |
| `get_location_raw(from_date, to_date)` | `GET /api/location/raw` | |
| **Weather (2)** | | |
| `get_weather()` | `GET /api/weather` | |
| `get_air_quality(site_id?)` | `GET /api/air-quality` | |
| **Memories (5)** | | |
| `create_memory(content, type, ...)` | `POST /api/memories` | |
| `list_memories(type?, search?, limit?)` | `GET /api/memories` | |
| `update_memory(memory_id, ...)` | `PUT /api/memories/{id}` | |
| `delete_memory(memory_id)` | `DELETE /api/memories/{id}` | |
| `reference_memory(memory_id)` | `POST /api/memories/{id}/reference` | |
| **Goals (4)** | | |
| `create_goal(name, ...)` | `POST /api/goals` | |
| `list_goals(status?)` | `GET /api/goals` | |
| `get_goal(goal_id)` | `GET /api/goals/{id}` | |
| `update_goal(goal_id, ...)` | `PUT /api/goals/{id}` | |
| **Analytics (2)** | | |
| `get_analytics_flags(severity?, ...)` | `GET /api/analytics/flags` | |
| `acknowledge_flag(flag_id)` | `PUT /api/analytics/flags/{id}/acknowledge` | |
| **Config (9)** | | |
| `list_schedules()` | `GET /api/config/schedules` | |
| `create_schedule(task_name, ...)` | `POST /api/config/schedules` | |
| `update_schedule(schedule_id, ...)` | `PUT /api/config/schedules/{id}` | |
| `list_settings()` | `GET /api/config/settings` | |
| `get_setting(key)` | `GET /api/config/settings/{key}` | |
| `set_setting(key, value)` | `PUT /api/config/settings/{key}` | |
| `list_monitored_items(category?)` | `GET /api/config/monitored-items` | |
| `create_monitored_item(category, ...)` | `POST /api/config/monitored-items` | |
| `delete_monitored_item(item_id)` | `DELETE /api/config/monitored-items/{id}` | |
| **Misc (6)** | | |
| `get_data_freshness()` | `GET /api/freshness` | |
| `get_storage()` | `GET /api/storage` | |
| `list_conversations()` | `GET /api/conversations` | |
| `get_conversation(session_id)` | `GET /api/conversations/{id}` | |
| `get_task_history(task_name?, limit?)` | `GET /api/tasks/history` | |
| `enqueue_vault_item(content_type, ...)` | `POST /api/vault-queue` | |

---

### Task 1: Project Scaffold & Configuration

**Files:**
- Create: `bede-data-mcp/pyproject.toml`
- Create: `bede-data-mcp/src/bede_data_mcp/__init__.py`
- Create: `bede-data-mcp/src/bede_data_mcp/config.py`
- Create: `bede-data-mcp/src/bede_data_mcp/client.py`
- Create: `bede-data-mcp/src/bede_data_mcp/server.py`
- Create: `bede-data-mcp/tests/__init__.py`
- Create: `bede-data-mcp/tests/conftest.py`
- Create: `bede-data-mcp/tests/test_client.py`

- [x] **Step 1: Create directory structure**

```bash
cd /Users/joeradford/dev/bede
mkdir -p bede-data-mcp/src/bede_data_mcp
mkdir -p bede-data-mcp/tests
touch bede-data-mcp/src/bede_data_mcp/__init__.py
touch bede-data-mcp/tests/__init__.py
```

- [x] **Step 2: Write pyproject.toml**

Create `bede-data-mcp/pyproject.toml`:

```toml
[project]
name = "bede-data-mcp"
version = "0.1.0"
description = "Thin MCP proxy forwarding tool calls to bede-data's HTTP API"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.28.0",
    "pydantic-settings>=2.7.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "ruff>=0.11.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/bede_data_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
```

- [x] **Step 3: Write config.py**

Create `bede-data-mcp/src/bede_data_mcp/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bede_data_url: str = "http://bede-data:8001"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
```

- [x] **Step 4: Write client.py**

Create `bede-data-mcp/src/bede_data_mcp/client.py`:

```python
import httpx

from bede_data_mcp.config import settings


async def _request(method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(base_url=settings.bede_data_url, timeout=30.0) as c:
            r = await c.request(method, path, params=params, json=body)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"bede-data returned {e.response.status_code}", "detail": e.response.text}
    except (httpx.ConnectError, httpx.TimeoutException):
        return {"error": "bede-data unavailable"}


async def get(path: str, **params) -> dict:
    p = {k: v for k, v in params.items() if v is not None}
    return await _request("GET", path, params=p)


async def post(path: str, body: dict | None = None) -> dict:
    return await _request("POST", path, body=body)


async def put(path: str, body: dict | None = None) -> dict:
    return await _request("PUT", path, body=body)


async def delete(path: str) -> dict:
    return await _request("DELETE", path)
```

- [x] **Step 5: Write server.py skeleton**

Create `bede-data-mcp/src/bede_data_mcp/server.py`:

```python
"""bede-data-mcp: Thin MCP proxy forwarding tool calls to bede-data's HTTP API."""

import os

from fastmcp import FastMCP

from bede_data_mcp import client

mcp = FastMCP("personal-data")


if __name__ == "__main__":
    port = int(os.environ.get("DATA_MCP_PORT", "8002"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
```

- [x] **Step 6: Write conftest.py**

Create `bede-data-mcp/tests/conftest.py`:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def api(monkeypatch):
    """Mock all HTTP client functions used by server.py tools."""
    mocks = SimpleNamespace(
        get=AsyncMock(),
        post=AsyncMock(),
        put=AsyncMock(),
        delete=AsyncMock(),
    )
    for name in ("get", "post", "put", "delete"):
        monkeypatch.setattr(f"bede_data_mcp.client.{name}", getattr(mocks, name))
    return mocks
```

- [x] **Step 7: Write client tests**

Create `bede-data-mcp/tests/test_client.py`:

```python
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bede_data_mcp import client


async def test_get_filters_none_params():
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.request.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_http):
        result = await client.get("/test", foo="bar", baz=None)

    mock_http.request.assert_called_once_with("GET", "/test", params={"foo": "bar"}, json=None)
    assert result == {"ok": True}


async def test_get_connection_error():
    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.request.side_effect = httpx.ConnectError("refused")

    with patch("httpx.AsyncClient", return_value=mock_http):
        result = await client.get("/test")

    assert result["error"] == "bede-data unavailable"


async def test_get_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=mock_response
    )

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.request.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_http):
        result = await client.get("/test")

    assert result["error"] == "bede-data returned 500"


async def test_post_sends_body():
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1}
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.request.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_http):
        result = await client.post("/test", {"key": "value"})

    mock_http.request.assert_called_once_with("POST", "/test", params=None, json={"key": "value"})
    assert result == {"id": 1}
```

- [x] **Step 8: Install dependencies and run tests**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv sync --extra dev
uv run pytest tests/ -v --tb=short
```

Expected: all 4 client tests pass.

- [x] **Step 9: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): project scaffold with config, HTTP client, and test fixtures"
```

---

### Task 2: Health Read Tools

**Files:**
- Create: `bede-data-mcp/tests/test_health_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write health tool tests**

Create `bede-data-mcp/tests/test_health_tools.py`:

```python
from bede_data_mcp.server import (
    get_activity,
    get_heart_rate,
    get_medications,
    get_sleep,
    get_wellbeing,
    get_workouts,
)


async def test_get_sleep(api):
    api.get.return_value = {"date": "2026-04-30", "total_hours": 7.5, "bedtime": "22:30", "wake_time": "06:00", "phases": []}
    result = await get_sleep("2026-04-30")
    api.get.assert_called_once_with("/api/health/sleep", date="2026-04-30", timezone="Australia/Sydney")
    assert result["total_hours"] == 7.5


async def test_get_sleep_custom_timezone(api):
    api.get.return_value = {"date": "2026-04-30", "total_hours": 8.0}
    await get_sleep("2026-04-30", timezone="America/New_York")
    api.get.assert_called_once_with("/api/health/sleep", date="2026-04-30", timezone="America/New_York")


async def test_get_activity(api):
    api.get.return_value = {"date": "2026-04-30", "steps": 8423, "active_energy": 512, "exercise_minutes": 38, "stand_hours": 10}
    result = await get_activity("2026-04-30")
    api.get.assert_called_once_with("/api/health/activity", date="2026-04-30", timezone="Australia/Sydney")
    assert result["steps"] == 8423


async def test_get_workouts(api):
    api.get.return_value = {"date": "2026-04-30", "workouts": [{"workout_type": "running", "duration_minutes": 30}]}
    result = await get_workouts("2026-04-30")
    api.get.assert_called_once_with("/api/health/workouts", date="2026-04-30", timezone="Australia/Sydney")
    assert len(result["workouts"]) == 1


async def test_get_heart_rate(api):
    api.get.return_value = {"date": "2026-04-30", "resting_heart_rate": 58, "heart_rate_variability": 42}
    result = await get_heart_rate("2026-04-30")
    api.get.assert_called_once_with("/api/health/heart-rate", date="2026-04-30", timezone="Australia/Sydney")
    assert result["resting_heart_rate"] == 58


async def test_get_wellbeing(api):
    api.get.return_value = {"date": "2026-04-30", "mindful_minutes": 10, "state_of_mind": []}
    result = await get_wellbeing("2026-04-30")
    api.get.assert_called_once_with("/api/health/wellbeing", date="2026-04-30", timezone="Australia/Sydney")
    assert result["mindful_minutes"] == 10


async def test_get_medications(api):
    api.get.return_value = {"date": "2026-04-30", "medications": [{"medication": "vitamin D", "quantity": 1}]}
    result = await get_medications("2026-04-30")
    api.get.assert_called_once_with("/api/health/medications", date="2026-04-30", timezone="Australia/Sydney")
    assert len(result["medications"]) == 1
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_health_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'get_sleep' from 'bede_data_mcp.server'`

- [x] **Step 3: Add health tools to server.py**

Add the following to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Health tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_sleep(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return sleep summary for the night ending on the given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/health/sleep", date=date, timezone=timezone)


@mcp.tool()
async def get_activity(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return daily activity summary (steps, active energy, exercise minutes, stand hours).

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/health/activity", date=date, timezone=timezone)


@mcp.tool()
async def get_workouts(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return workouts recorded on a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/health/workouts", date=date, timezone=timezone)


@mcp.tool()
async def get_heart_rate(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return resting heart rate and HRV for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/health/heart-rate", date=date, timezone=timezone)


@mcp.tool()
async def get_wellbeing(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return mindfulness minutes and state of mind data for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/health/wellbeing", date=date, timezone=timezone)


@mcp.tool()
async def get_medications(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return medications logged on a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/health/medications", date=date, timezone=timezone)
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_health_tools.py -v --tb=short
```

Expected: all 7 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add health read tools (sleep, activity, workouts, heart rate, wellbeing, medications)"
```

---

### Task 3: Vault Data Read Tools

**Files:**
- Create: `bede-data-mcp/tests/test_vault_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write vault data tool tests**

Create `bede-data-mcp/tests/test_vault_tools.py`:

```python
from bede_data_mcp.server import (
    get_bede_sessions,
    get_claude_sessions,
    get_podcasts,
    get_safari_history,
    get_screen_time,
    get_youtube_history,
)


async def test_get_screen_time(api):
    api.get.return_value = {"date": "2026-04-30", "entries": [{"name": "Safari", "seconds": 3420}]}
    result = await get_screen_time("2026-04-30")
    api.get.assert_called_once_with("/api/vault/screen-time", date="2026-04-30", timezone="Australia/Sydney")
    assert len(result["entries"]) == 1


async def test_get_screen_time_with_filters(api):
    api.get.return_value = {"date": "2026-04-30", "entries": []}
    await get_screen_time("2026-04-30", device="iphone", top_n=5)
    api.get.assert_called_once_with("/api/vault/screen-time", date="2026-04-30", device="iphone", top_n=5, timezone="Australia/Sydney")


async def test_get_safari_history(api):
    api.get.return_value = {"date": "2026-04-30", "entries": [{"domain": "github.com", "title": "PR #42"}]}
    result = await get_safari_history("2026-04-30")
    api.get.assert_called_once_with("/api/vault/safari", date="2026-04-30", timezone="Australia/Sydney")
    assert result["entries"][0]["domain"] == "github.com"


async def test_get_safari_history_with_domain_filter(api):
    api.get.return_value = {"date": "2026-04-30", "entries": []}
    await get_safari_history("2026-04-30", device="mac", domain_filter="github.com", top_n=10)
    api.get.assert_called_once_with("/api/vault/safari", date="2026-04-30", device="mac", domain="github.com", top_n=10, timezone="Australia/Sydney")


async def test_get_youtube_history(api):
    api.get.return_value = {"date": "2026-04-30", "entries": [{"title": "Tech Talk", "url": "https://youtube.com/watch?v=abc"}]}
    result = await get_youtube_history("2026-04-30")
    api.get.assert_called_once_with("/api/vault/youtube", date="2026-04-30", timezone="Australia/Sydney")
    assert len(result["entries"]) == 1


async def test_get_podcasts(api):
    api.get.return_value = {"date": "2026-04-30", "entries": [{"podcast": "The Daily", "episode": "Episode 1"}]}
    result = await get_podcasts("2026-04-30")
    api.get.assert_called_once_with("/api/vault/podcasts", date="2026-04-30", timezone="Australia/Sydney")
    assert result["entries"][0]["podcast"] == "The Daily"


async def test_get_claude_sessions(api):
    api.get.return_value = {"date": "2026-04-30", "sessions": [{"project": "bede", "duration_min": 45}]}
    result = await get_claude_sessions("2026-04-30")
    api.get.assert_called_once_with("/api/vault/claude-sessions", date="2026-04-30", timezone="Australia/Sydney")
    assert result["sessions"][0]["project"] == "bede"


async def test_get_bede_sessions(api):
    api.get.return_value = {"date": "2026-04-30", "sessions": [{"task_name": "morning_briefing", "duration_min": 5}]}
    result = await get_bede_sessions("2026-04-30")
    api.get.assert_called_once_with("/api/vault/bede-sessions", date="2026-04-30", timezone="Australia/Sydney")
    assert result["sessions"][0]["task_name"] == "morning_briefing"
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_vault_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'get_screen_time' from 'bede_data_mcp.server'`

- [x] **Step 3: Add vault data tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Vault data tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_screen_time(
    date: str,
    device: str | None = None,
    top_n: int | None = None,
    timezone: str = "Australia/Sydney",
) -> dict:
    """Return app and web domain screen time usage for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        device: 'mac', 'iphone', or omit for all devices.
        top_n: Return only the top N entries by duration.
        timezone: Olson timezone name.
    """
    return await client.get("/api/vault/screen-time", date=date, device=device, top_n=top_n, timezone=timezone)


@mcp.tool()
async def get_safari_history(
    date: str,
    device: str | None = None,
    domain_filter: str | None = None,
    top_n: int | None = None,
    timezone: str = "Australia/Sydney",
) -> dict:
    """Return Safari page visits for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        device: 'mac', 'iphone', or omit for all devices.
        domain_filter: Filter by domain substring (e.g. 'github.com').
        top_n: Limit number of results.
        timezone: Olson timezone name.
    """
    return await client.get("/api/vault/safari", date=date, device=device, domain=domain_filter, top_n=top_n, timezone=timezone)


@mcp.tool()
async def get_youtube_history(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return YouTube page visits for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/vault/youtube", date=date, timezone=timezone)


@mcp.tool()
async def get_podcasts(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return podcast episodes played on a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/vault/podcasts", date=date, timezone=timezone)


@mcp.tool()
async def get_claude_sessions(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return Claude Code session summaries for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/vault/claude-sessions", date=date, timezone=timezone)


@mcp.tool()
async def get_bede_sessions(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return Bede (Telegram AI assistant) session summaries for a given local date.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/vault/bede-sessions", date=date, timezone=timezone)
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_vault_tools.py -v --tb=short
```

Expected: all 8 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add vault data tools (screen time, safari, youtube, podcasts, sessions)"
```

---

### Task 4: Location & Weather Read Tools

**Files:**
- Create: `bede-data-mcp/tests/test_location_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write location & weather tool tests**

Create `bede-data-mcp/tests/test_location_tools.py`:

```python
from bede_data_mcp.server import (
    get_air_quality,
    get_location_raw,
    get_location_summary,
    get_weather,
)


async def test_get_location_summary(api):
    api.get.return_value = {"date": "2026-04-30", "stops": [{"name": "Home", "arrived": "08:00"}]}
    result = await get_location_summary("2026-04-30")
    api.get.assert_called_once_with("/api/location/summary", date="2026-04-30", tz="Australia/Sydney")
    assert result["stops"][0]["name"] == "Home"


async def test_get_location_summary_custom_timezone(api):
    api.get.return_value = {"date": "2026-04-30", "stops": []}
    await get_location_summary("2026-04-30", timezone="America/New_York")
    api.get.assert_called_once_with("/api/location/summary", date="2026-04-30", tz="America/New_York")


async def test_get_location_raw(api):
    api.get.return_value = {"from_date": "2026-04-29", "to_date": "2026-04-30", "points": [{"lat": -33.8, "lon": 151.2}]}
    result = await get_location_raw("2026-04-29", "2026-04-30")
    api.get.assert_called_once_with("/api/location/raw", from_date="2026-04-29", to_date="2026-04-30")
    assert len(result["points"]) == 1


async def test_get_weather(api):
    api.get.return_value = {"temperature": 22, "conditions": "Partly cloudy"}
    result = await get_weather()
    api.get.assert_called_once_with("/api/weather")
    assert result["temperature"] == 22


async def test_get_air_quality(api):
    api.get.return_value = {"aqi": 42, "category": "Good"}
    result = await get_air_quality()
    api.get.assert_called_once_with("/api/air-quality")
    assert result["aqi"] == 42


async def test_get_air_quality_with_site(api):
    api.get.return_value = {"aqi": 55, "site_id": "parramatta"}
    await get_air_quality(site_id="parramatta")
    api.get.assert_called_once_with("/api/air-quality", site_id="parramatta")
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_location_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'get_location_summary' from 'bede_data_mcp.server'`

- [x] **Step 3: Add location & weather tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Location tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_location_summary(date: str, timezone: str = "Australia/Sydney") -> dict:
    """Return summarised stops for a given local date with place names and arrival/departure times.

    Clusters GPS points into named locations via reverse geocoding.

    Args:
        date: Local date -- 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await client.get("/api/location/summary", date=date, tz=timezone)


@mcp.tool()
async def get_location_raw(from_date: str, to_date: str) -> dict:
    """Return raw GPS points for a local date range without summarisation.

    Args:
        from_date: Start local date ('YYYY-MM-DD').
        to_date: End local date ('YYYY-MM-DD').
    """
    return await client.get("/api/location/raw", from_date=from_date, to_date=to_date)


# ---------------------------------------------------------------------------
# Weather tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_weather() -> dict:
    """Return current weather observations and 7-day forecast for the configured location.

    Includes temperature, conditions, wind, humidity, rain chance, UV index, and sunrise/sunset.
    Data sourced from the Australian Bureau of Meteorology.
    """
    return await client.get("/api/weather")


@mcp.tool()
async def get_air_quality(site_id: str | None = None) -> dict:
    """Return current air quality index and alerts.

    Args:
        site_id: Optional monitoring site ID. Omit for default location.
    """
    return await client.get("/api/air-quality", site_id=site_id)
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_location_tools.py -v --tb=short
```

Expected: all 6 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add location and weather tools"
```

---

### Task 5: Memory CRUD Tools

**Files:**
- Create: `bede-data-mcp/tests/test_memory_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write memory tool tests**

Create `bede-data-mcp/tests/test_memory_tools.py`:

```python
from bede_data_mcp.server import (
    create_memory,
    delete_memory,
    list_memories,
    reference_memory,
    update_memory,
)


async def test_create_memory(api):
    api.post.return_value = {"id": 1, "content": "Training for marathon", "type": "fact", "active": True}
    result = await create_memory("Training for marathon", "fact")
    api.post.assert_called_once_with("/api/memories", {"content": "Training for marathon", "type": "fact"})
    assert result["id"] == 1


async def test_create_memory_with_supersedes(api):
    api.post.return_value = {"id": 2, "content": "Half-marathon, not full", "type": "correction", "active": True}
    await create_memory("Half-marathon, not full", "correction", supersedes=1)
    api.post.assert_called_once_with("/api/memories", {"content": "Half-marathon, not full", "type": "correction", "supersedes": 1})


async def test_create_memory_with_source(api):
    api.post.return_value = {"id": 3, "content": "Likes camping", "type": "fact"}
    await create_memory("Likes camping", "fact", source_conversation="session-abc")
    api.post.assert_called_once_with("/api/memories", {"content": "Likes camping", "type": "fact", "source_conversation": "session-abc"})


async def test_list_memories(api):
    api.get.return_value = {"memories": [{"id": 1, "content": "Training for marathon"}]}
    result = await list_memories()
    api.get.assert_called_once_with("/api/memories")
    assert len(result["memories"]) == 1


async def test_list_memories_with_filters(api):
    api.get.return_value = {"memories": []}
    await list_memories(type="fact", search="marathon", limit=10)
    api.get.assert_called_once_with("/api/memories", type="fact", search="marathon", limit=10)


async def test_update_memory(api):
    api.put.return_value = {"id": 1, "content": "Updated content", "type": "fact"}
    result = await update_memory(1, content="Updated content")
    api.put.assert_called_once_with("/api/memories/1", {"content": "Updated content"})
    assert result["content"] == "Updated content"


async def test_update_memory_type(api):
    api.put.return_value = {"id": 1, "content": "Same", "type": "preference"}
    await update_memory(1, type="preference")
    api.put.assert_called_once_with("/api/memories/1", {"type": "preference"})


async def test_delete_memory(api):
    api.delete.return_value = {"status": "deleted", "id": 1}
    result = await delete_memory(1)
    api.delete.assert_called_once_with("/api/memories/1")
    assert result["status"] == "deleted"


async def test_reference_memory(api):
    api.post.return_value = {"id": 1, "last_referenced_at": "2026-04-30T10:00:00Z"}
    result = await reference_memory(1)
    api.post.assert_called_once_with("/api/memories/1/reference")
    assert "last_referenced_at" in result
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_memory_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'create_memory' from 'bede_data_mcp.server'`

- [x] **Step 3: Add memory tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Memory tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_memory(
    content: str,
    type: str,
    source_conversation: str | None = None,
    supersedes: int | None = None,
) -> dict:
    """Store a new memory. Memories are facts, preferences, or corrections that persist across conversations.

    Args:
        content: The memory content to store.
        type: Memory type -- 'fact', 'preference', 'correction', or 'commitment'.
        source_conversation: Optional session ID of the conversation that produced this memory.
        supersedes: Optional ID of a previous memory this one corrects (marks the old one inactive).
    """
    body: dict = {"content": content, "type": type}
    if source_conversation is not None:
        body["source_conversation"] = source_conversation
    if supersedes is not None:
        body["supersedes"] = supersedes
    return await client.post("/api/memories", body)


@mcp.tool()
async def list_memories(
    type: str | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> dict:
    """List active memories, optionally filtered by type or search term.

    Args:
        type: Filter by type -- 'fact', 'preference', 'correction', or 'commitment'.
        search: Search term to filter memory content.
        limit: Maximum number of memories to return.
    """
    return await client.get("/api/memories", type=type, search=search, limit=limit)


@mcp.tool()
async def update_memory(
    memory_id: int,
    content: str | None = None,
    type: str | None = None,
) -> dict:
    """Update an existing memory's content or type.

    Args:
        memory_id: ID of the memory to update.
        content: New content (omit to keep current).
        type: New type (omit to keep current).
    """
    body: dict = {}
    if content is not None:
        body["content"] = content
    if type is not None:
        body["type"] = type
    return await client.put(f"/api/memories/{memory_id}", body)


@mcp.tool()
async def delete_memory(memory_id: int) -> dict:
    """Soft-delete a memory (marks it inactive, does not remove the row).

    Args:
        memory_id: ID of the memory to delete.
    """
    return await client.delete(f"/api/memories/{memory_id}")


@mcp.tool()
async def reference_memory(memory_id: int) -> dict:
    """Touch a memory's last-referenced timestamp for relevance ranking.

    Call this when a memory is actively used in a conversation to track which memories are still relevant.

    Args:
        memory_id: ID of the memory being referenced.
    """
    return await client.post(f"/api/memories/{memory_id}/reference")
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_memory_tools.py -v --tb=short
```

Expected: all 9 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add memory CRUD tools (create, list, update, delete, reference)"
```

---

### Task 6: Goal CRUD Tools

**Files:**
- Create: `bede-data-mcp/tests/test_goal_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write goal tool tests**

Create `bede-data-mcp/tests/test_goal_tools.py`:

```python
from bede_data_mcp.server import create_goal, get_goal, list_goals, update_goal


async def test_create_goal(api):
    api.post.return_value = {"id": 1, "name": "Read 2 books in May", "status": "active"}
    result = await create_goal("Read 2 books in May")
    api.post.assert_called_once_with("/api/goals", {"name": "Read 2 books in May"})
    assert result["id"] == 1


async def test_create_goal_with_details(api):
    api.post.return_value = {"id": 2, "name": "AWS cert", "deadline": "2026-09-01"}
    await create_goal(
        "AWS cert",
        description="Pass AWS Solutions Architect Associate",
        deadline="2026-09-01",
        measurable_indicators="Pass the exam",
    )
    api.post.assert_called_once_with("/api/goals", {
        "name": "AWS cert",
        "description": "Pass AWS Solutions Architect Associate",
        "deadline": "2026-09-01",
        "measurable_indicators": "Pass the exam",
    })


async def test_list_goals(api):
    api.get.return_value = {"goals": [{"id": 1, "name": "Read 2 books", "status": "active"}]}
    result = await list_goals()
    api.get.assert_called_once_with("/api/goals")
    assert len(result["goals"]) == 1


async def test_list_goals_by_status(api):
    api.get.return_value = {"goals": []}
    await list_goals(status="completed")
    api.get.assert_called_once_with("/api/goals", status="completed")


async def test_get_goal(api):
    api.get.return_value = {"id": 1, "name": "Read 2 books", "status": "active"}
    result = await get_goal(1)
    api.get.assert_called_once_with("/api/goals/1")
    assert result["name"] == "Read 2 books"


async def test_update_goal(api):
    api.put.return_value = {"id": 1, "name": "Read 3 books", "status": "active"}
    result = await update_goal(1, name="Read 3 books")
    api.put.assert_called_once_with("/api/goals/1", {"name": "Read 3 books"})
    assert result["name"] == "Read 3 books"


async def test_update_goal_status(api):
    api.put.return_value = {"id": 1, "name": "Read 2 books", "status": "completed"}
    await update_goal(1, status="completed")
    api.put.assert_called_once_with("/api/goals/1", {"status": "completed"})


async def test_update_goal_deadline(api):
    api.put.return_value = {"id": 1, "deadline": "2026-12-31"}
    await update_goal(1, deadline="2026-12-31")
    api.put.assert_called_once_with("/api/goals/1", {"deadline": "2026-12-31"})
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_goal_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'create_goal' from 'bede_data_mcp.server'`

- [x] **Step 3: Add goal tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Goal tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_goal(
    name: str,
    description: str | None = None,
    deadline: str | None = None,
    measurable_indicators: str | None = None,
) -> dict:
    """Create a new goal. Goals are commitments the user wants to track and be held accountable for.

    Args:
        name: Short name for the goal.
        description: Detailed description of what achieving this goal means.
        deadline: Target date ('YYYY-MM-DD') or omit for open-ended goals.
        measurable_indicators: How progress or completion will be measured.
    """
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    if deadline is not None:
        body["deadline"] = deadline
    if measurable_indicators is not None:
        body["measurable_indicators"] = measurable_indicators
    return await client.post("/api/goals", body)


@mcp.tool()
async def list_goals(status: str | None = None) -> dict:
    """List goals, optionally filtered by status.

    Args:
        status: Filter by status -- 'active', 'completed', or 'dropped'.
    """
    return await client.get("/api/goals", status=status)


@mcp.tool()
async def get_goal(goal_id: int) -> dict:
    """Get a single goal by ID.

    Args:
        goal_id: ID of the goal to retrieve.
    """
    return await client.get(f"/api/goals/{goal_id}")


@mcp.tool()
async def update_goal(
    goal_id: int,
    name: str | None = None,
    description: str | None = None,
    deadline: str | None = None,
    measurable_indicators: str | None = None,
    status: str | None = None,
) -> dict:
    """Update an existing goal's details or status.

    Args:
        goal_id: ID of the goal to update.
        name: New name (omit to keep current).
        description: New description (omit to keep current).
        deadline: New deadline date (omit to keep current).
        measurable_indicators: Updated measurement criteria (omit to keep current).
        status: New status -- 'active', 'completed', or 'dropped' (omit to keep current).
    """
    body: dict = {}
    for field in ("name", "description", "deadline", "measurable_indicators", "status"):
        val = locals()[field]
        if val is not None:
            body[field] = val
    return await client.put(f"/api/goals/{goal_id}", body)
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_goal_tools.py -v --tb=short
```

Expected: all 8 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add goal CRUD tools (create, list, get, update)"
```

---

### Task 7: Analytics Tools

**Files:**
- Create: `bede-data-mcp/tests/test_analytics_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write analytics tool tests**

Create `bede-data-mcp/tests/test_analytics_tools.py`:

```python
from bede_data_mcp.server import acknowledge_flag, get_analytics_flags


async def test_get_analytics_flags(api):
    api.get.return_value = {"flags": [{"id": 1, "signal": "sleep_declining", "severity": "concern"}]}
    result = await get_analytics_flags()
    api.get.assert_called_once_with("/api/analytics/flags")
    assert result["flags"][0]["signal"] == "sleep_declining"


async def test_get_analytics_flags_with_filters(api):
    api.get.return_value = {"flags": []}
    await get_analytics_flags(severity="alert", acknowledged=False, limit=10)
    api.get.assert_called_once_with("/api/analytics/flags", severity="alert", acknowledged=False, limit=10)


async def test_acknowledge_flag(api):
    api.put.return_value = {"id": 1, "signal": "sleep_declining", "acknowledged": True}
    result = await acknowledge_flag(1)
    api.put.assert_called_once_with("/api/analytics/flags/1/acknowledge")
    assert result["acknowledged"] is True
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_analytics_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'get_analytics_flags' from 'bede_data_mcp.server'`

- [x] **Step 3: Add analytics tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Analytics tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_analytics_flags(
    severity: str | None = None,
    acknowledged: bool | None = None,
    limit: int | None = None,
) -> dict:
    """Get computed analytics flags (wellbeing signals, goal staleness, etc.).

    Flags are produced by the Analytics Engine from raw data. Use these to understand
    patterns and trends that inform coaching conversations.

    Args:
        severity: Filter by severity -- 'info', 'nudge', 'concern', or 'alert'.
        acknowledged: Filter by acknowledgement status (true/false).
        limit: Maximum number of flags to return.
    """
    return await client.get("/api/analytics/flags", severity=severity, acknowledged=acknowledged, limit=limit)


@mcp.tool()
async def acknowledge_flag(flag_id: int) -> dict:
    """Mark an analytics flag as acknowledged so it is not raised again.

    Args:
        flag_id: ID of the flag to acknowledge.
    """
    return await client.put(f"/api/analytics/flags/{flag_id}/acknowledge")
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_analytics_tools.py -v --tb=short
```

Expected: all 3 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add analytics tools (get flags, acknowledge)"
```

---

### Task 8: Config Management Tools

**Files:**
- Create: `bede-data-mcp/tests/test_config_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write config tool tests**

Create `bede-data-mcp/tests/test_config_tools.py`:

```python
from bede_data_mcp.server import (
    create_monitored_item,
    create_schedule,
    delete_monitored_item,
    get_setting,
    list_monitored_items,
    list_schedules,
    list_settings,
    set_setting,
    update_schedule,
)


# --- Schedules ---


async def test_list_schedules(api):
    api.get.return_value = {"schedules": [{"id": 1, "task_name": "morning_briefing"}]}
    result = await list_schedules()
    api.get.assert_called_once_with("/api/config/schedules")
    assert len(result["schedules"]) == 1


async def test_create_schedule(api):
    api.post.return_value = {"id": 1, "task_name": "morning_briefing", "cron_expression": "0 8 * * 1-5"}
    result = await create_schedule("morning_briefing", "0 8 * * 1-5", "Deliver the morning briefing")
    api.post.assert_called_once_with("/api/config/schedules", {
        "task_name": "morning_briefing",
        "cron_expression": "0 8 * * 1-5",
        "prompt": "Deliver the morning briefing",
    })
    assert result["task_name"] == "morning_briefing"


async def test_create_schedule_with_options(api):
    api.post.return_value = {"id": 2, "task_name": "reflection"}
    await create_schedule(
        "reflection", "0 21 * * *", "Evening reflection",
        model="opus", timeout_seconds=600, interactive=True, enabled=True,
    )
    api.post.assert_called_once_with("/api/config/schedules", {
        "task_name": "reflection",
        "cron_expression": "0 21 * * *",
        "prompt": "Evening reflection",
        "model": "opus",
        "timeout_seconds": 600,
        "interactive": True,
        "enabled": True,
    })


async def test_update_schedule(api):
    api.put.return_value = {"id": 1, "cron_expression": "0 7 * * 1-5"}
    result = await update_schedule(1, cron_expression="0 7 * * 1-5")
    api.put.assert_called_once_with("/api/config/schedules/1", {"cron_expression": "0 7 * * 1-5"})
    assert result["cron_expression"] == "0 7 * * 1-5"


async def test_update_schedule_enabled(api):
    api.put.return_value = {"id": 1, "enabled": False}
    await update_schedule(1, enabled=False)
    api.put.assert_called_once_with("/api/config/schedules/1", {"enabled": False})


# --- Settings ---


async def test_list_settings(api):
    api.get.return_value = {"settings": [{"key": "quiet_hours_start", "value": "22:00"}]}
    result = await list_settings()
    api.get.assert_called_once_with("/api/config/settings")
    assert len(result["settings"]) == 1


async def test_get_setting(api):
    api.get.return_value = {"key": "quiet_hours_start", "value": "22:00"}
    result = await get_setting("quiet_hours_start")
    api.get.assert_called_once_with("/api/config/settings/quiet_hours_start")
    assert result["value"] == "22:00"


async def test_set_setting(api):
    api.put.return_value = {"key": "quiet_hours_start", "value": "23:00"}
    result = await set_setting("quiet_hours_start", "23:00")
    api.put.assert_called_once_with("/api/config/settings/quiet_hours_start", {"value": "23:00"})
    assert result["value"] == "23:00"


# --- Monitored Items ---


async def test_list_monitored_items(api):
    api.get.return_value = {"items": [{"id": 1, "category": "deals", "name": "camping gear"}]}
    result = await list_monitored_items()
    api.get.assert_called_once_with("/api/config/monitored-items")
    assert len(result["items"]) == 1


async def test_list_monitored_items_by_category(api):
    api.get.return_value = {"items": []}
    await list_monitored_items(category="deals")
    api.get.assert_called_once_with("/api/config/monitored-items", category="deals")


async def test_create_monitored_item(api):
    api.post.return_value = {"id": 1, "category": "deals", "name": "camping gear", "config": "{}"}
    result = await create_monitored_item("deals", "camping gear", "{}")
    api.post.assert_called_once_with("/api/config/monitored-items", {
        "category": "deals", "name": "camping gear", "config": "{}",
    })
    assert result["id"] == 1


async def test_delete_monitored_item(api):
    api.delete.return_value = {"status": "deleted", "id": 1}
    result = await delete_monitored_item(1)
    api.delete.assert_called_once_with("/api/config/monitored-items/1")
    assert result["status"] == "deleted"
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_config_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'list_schedules' from 'bede_data_mcp.server'`

- [x] **Step 3: Add config tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Config tools — schedules
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_schedules() -> dict:
    """List all scheduled task definitions."""
    return await client.get("/api/config/schedules")


@mcp.tool()
async def create_schedule(
    task_name: str,
    cron_expression: str,
    prompt: str,
    model: str | None = None,
    timeout_seconds: int | None = None,
    interactive: bool | None = None,
    enabled: bool | None = None,
) -> dict:
    """Create a new scheduled task.

    Args:
        task_name: Unique name for the task.
        cron_expression: Cron schedule (e.g. '0 8 * * 1-5' for weekday mornings at 8am).
        prompt: The prompt text sent to Claude when the task fires.
        model: Claude model to use (omit for default).
        timeout_seconds: Maximum execution time in seconds (omit for default 300).
        interactive: Whether the task can yield to the user for input (omit for default false).
        enabled: Whether the task is active (omit for default true).
    """
    body: dict = {"task_name": task_name, "cron_expression": cron_expression, "prompt": prompt}
    for field in ("model", "timeout_seconds", "interactive", "enabled"):
        val = locals()[field]
        if val is not None:
            body[field] = val
    return await client.post("/api/config/schedules", body)


@mcp.tool()
async def update_schedule(
    schedule_id: int,
    cron_expression: str | None = None,
    prompt: str | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    interactive: bool | None = None,
    enabled: bool | None = None,
) -> dict:
    """Update an existing scheduled task.

    Args:
        schedule_id: ID of the schedule to update.
        cron_expression: New cron schedule (omit to keep current).
        prompt: New prompt text (omit to keep current).
        model: New model (omit to keep current).
        timeout_seconds: New timeout (omit to keep current).
        interactive: New interactive setting (omit to keep current).
        enabled: New enabled setting (omit to keep current).
    """
    body: dict = {}
    for field in ("cron_expression", "prompt", "model", "timeout_seconds", "interactive", "enabled"):
        val = locals()[field]
        if val is not None:
            body[field] = val
    return await client.put(f"/api/config/schedules/{schedule_id}", body)


# ---------------------------------------------------------------------------
# Config tools — settings
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_settings() -> dict:
    """List all key-value settings (quiet hours, coaching thresholds, etc.)."""
    return await client.get("/api/config/settings")


@mcp.tool()
async def get_setting(key: str) -> dict:
    """Get a single setting by key.

    Args:
        key: The setting key (e.g. 'quiet_hours_start', 'sleep_target_hours').
    """
    return await client.get(f"/api/config/settings/{key}")


@mcp.tool()
async def set_setting(key: str, value: str) -> dict:
    """Set a key-value setting. Creates or updates.

    Args:
        key: The setting key.
        value: The setting value (stored as a string).
    """
    return await client.put(f"/api/config/settings/{key}", {"value": value})


# ---------------------------------------------------------------------------
# Config tools — monitored items
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_monitored_items(category: str | None = None) -> dict:
    """List monitored items (deal categories, content sources, etc.).

    Args:
        category: Filter by category (e.g. 'deals', 'news').
    """
    return await client.get("/api/config/monitored-items", category=category)


@mcp.tool()
async def create_monitored_item(category: str, name: str, config: str) -> dict:
    """Add a new monitored item (e.g. a deal category to track or a news source).

    Args:
        category: Item category (e.g. 'deals', 'news').
        name: Human-readable name.
        config: JSON string with category-specific configuration.
    """
    return await client.post("/api/config/monitored-items", {"category": category, "name": name, "config": config})


@mcp.tool()
async def delete_monitored_item(item_id: int) -> dict:
    """Remove a monitored item (soft-delete).

    Args:
        item_id: ID of the item to remove.
    """
    return await client.delete(f"/api/config/monitored-items/{item_id}")
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_config_tools.py -v --tb=short
```

Expected: all 13 tests PASS.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add config management tools (schedules, settings, monitored items)"
```

---

### Task 9: Miscellaneous Tools

**Files:**
- Create: `bede-data-mcp/tests/test_misc_tools.py`
- Modify: `bede-data-mcp/src/bede_data_mcp/server.py`

- [x] **Step 1: Write misc tool tests**

Create `bede-data-mcp/tests/test_misc_tools.py`:

```python
from bede_data_mcp.server import (
    enqueue_vault_item,
    get_conversation,
    get_data_freshness,
    get_storage,
    get_task_history,
    list_conversations,
)


async def test_get_data_freshness(api):
    api.get.return_value = {"sources": [{"source": "health", "last_received_at": "2026-04-30T06:00:00Z"}]}
    result = await get_data_freshness()
    api.get.assert_called_once_with("/api/freshness")
    assert len(result["sources"]) == 1


async def test_get_storage(api):
    api.get.return_value = {"db_size_bytes": 1048576, "tables": [{"name": "health_metrics", "row_count": 500}]}
    result = await get_storage()
    api.get.assert_called_once_with("/api/storage")
    assert result["db_size_bytes"] == 1048576


async def test_list_conversations(api):
    api.get.return_value = {"sessions": [{"session_id": "abc123", "message_count": 42}]}
    result = await list_conversations()
    api.get.assert_called_once_with("/api/conversations")
    assert result["sessions"][0]["session_id"] == "abc123"


async def test_get_conversation(api):
    api.get.return_value = {"session_id": "abc123", "messages": [{"role": "user", "content": "hello"}]}
    result = await get_conversation("abc123")
    api.get.assert_called_once_with("/api/conversations/abc123")
    assert len(result["messages"]) == 1


async def test_get_task_history(api):
    api.get.return_value = {"executions": [{"task_name": "morning_briefing", "status": "success"}]}
    result = await get_task_history()
    api.get.assert_called_once_with("/api/tasks/history")
    assert result["executions"][0]["status"] == "success"


async def test_get_task_history_with_filters(api):
    api.get.return_value = {"executions": []}
    await get_task_history(task_name="morning_briefing", limit=10)
    api.get.assert_called_once_with("/api/tasks/history", task_name="morning_briefing", limit=10)


async def test_enqueue_vault_item(api):
    api.post.return_value = {"id": 1, "content_type": "journal", "status": "pending"}
    result = await enqueue_vault_item("journal", "# April 30\n\nGood day.")
    api.post.assert_called_once_with("/api/vault-queue", {"content_type": "journal", "content": "# April 30\n\nGood day."})
    assert result["status"] == "pending"


async def test_enqueue_vault_item_with_path(api):
    api.post.return_value = {"id": 2, "vault_path": "Journal/2026-04-30.md"}
    await enqueue_vault_item("journal", "content", vault_path="Journal/2026-04-30.md")
    api.post.assert_called_once_with("/api/vault-queue", {
        "content_type": "journal", "content": "content", "vault_path": "Journal/2026-04-30.md",
    })
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_misc_tools.py -v --tb=short
```

Expected: FAIL — `ImportError: cannot import name 'get_data_freshness' from 'bede_data_mcp.server'`

- [x] **Step 3: Add misc tools to server.py**

Add the following section to `bede-data-mcp/src/bede_data_mcp/server.py`, before the `if __name__` guard:

```python
# ---------------------------------------------------------------------------
# Data pipeline tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_data_freshness() -> dict:
    """Return data freshness status for all sources (when each source last received data)."""
    return await client.get("/api/freshness")


@mcp.tool()
async def get_storage() -> dict:
    """Return database storage usage: total size and row counts per table."""
    return await client.get("/api/storage")


# ---------------------------------------------------------------------------
# Conversation history tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_conversations() -> dict:
    """List all past conversation sessions with metadata (message count, first timestamp)."""
    return await client.get("/api/conversations")


@mcp.tool()
async def get_conversation(session_id: str) -> dict:
    """Get the full transcript of a past conversation session.

    Args:
        session_id: The session ID to retrieve.
    """
    return await client.get(f"/api/conversations/{session_id}")


# ---------------------------------------------------------------------------
# Task history tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_task_history(task_name: str | None = None, limit: int | None = None) -> dict:
    """Get scheduled task execution history.

    Args:
        task_name: Filter by task name (omit for all tasks).
        limit: Maximum number of records to return.
    """
    return await client.get("/api/tasks/history", task_name=task_name, limit=limit)


# ---------------------------------------------------------------------------
# Vault publish queue
# ---------------------------------------------------------------------------


@mcp.tool()
async def enqueue_vault_item(content_type: str, content: str, vault_path: str | None = None) -> dict:
    """Queue content for publishing to the Obsidian vault.

    Use this for journal entries, captured ideas, or any content the user wants in their vault.
    A background process picks items off the queue and writes them as Markdown files.

    Args:
        content_type: Type of content (e.g. 'journal', 'idea', 'note').
        content: The Markdown content to publish.
        vault_path: Target path within the vault (e.g. 'Journal/2026-04-30.md'). Optional.
    """
    body: dict = {"content_type": content_type, "content": content}
    if vault_path is not None:
        body["vault_path"] = vault_path
    return await client.post("/api/vault-queue", body)
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/test_misc_tools.py -v --tb=short
```

Expected: all 8 tests PASS.

- [x] **Step 5: Run full test suite**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run pytest tests/ -v --tb=short
```

Expected: all tests PASS across all test files.

- [x] **Step 6: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/
git commit -m "feat(bede-data-mcp): add misc tools (freshness, storage, conversations, task history, vault queue)"
```

---

### Task 10: Dockerfile & CI Workflow

**Files:**
- Create: `bede-data-mcp/Dockerfile`
- Create: `.github/workflows/bede-data-mcp-ci.yml` (in bede repo)

- [x] **Step 1: Write Dockerfile**

Create `bede-data-mcp/Dockerfile`:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY src/ src/

RUN uv sync --no-dev

RUN useradd --create-home --uid 1000 bede
USER bede

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('localhost', 8002), timeout=5); s.close()" || exit 1

CMD [".venv/bin/python", "-m", "bede_data_mcp"]
```

- [x] **Step 2: Add `__main__.py` for module execution**

Create `bede-data-mcp/src/bede_data_mcp/__main__.py`:

```python
from bede_data_mcp.server import mcp

import os

port = int(os.environ.get("DATA_MCP_PORT", "8002"))
mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
```

- [x] **Step 3: Write CI workflow**

Create `.github/workflows/bede-data-mcp-ci.yml` (in the bede repo):

```yaml
name: bede-data-mcp CI

on:
  workflow_dispatch:
  pull_request:
    paths:
      - "bede-data-mcp/**"
  push:
    branches: [main]
    paths:
      - "bede-data-mcp/**"

defaults:
  run:
    working-directory: bede-data-mcp

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --extra dev
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --extra dev
      - run: uv run pytest tests/ -v --tb=short

  build-push:
    if: (github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == 'refs/heads/main'
    needs: [lint, test]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-buildx-action@v3

      - uses: docker/build-push-action@v6
        with:
          context: ./bede-data-mcp
          push: true
          platforms: linux/amd64
          tags: |
            ghcr.io/josephradford/bede-data-mcp:latest
            ghcr.io/josephradford/bede-data-mcp:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [x] **Step 4: Verify lint passes**

```bash
cd /Users/joeradford/dev/bede/bede-data-mcp
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: no errors. If ruff reports formatting issues, run `uv run ruff format src/ tests/` to fix.

- [x] **Step 5: Commit**

```bash
cd /Users/joeradford/dev/bede
git add bede-data-mcp/Dockerfile bede-data-mcp/src/bede_data_mcp/__main__.py .github/workflows/bede-data-mcp-ci.yml
git commit -m "feat(bede-data-mcp): add Dockerfile and CI workflow"
```

---

### Task 11: Docker Compose Integration & Documentation

**Files:**
- Modify: `docker-compose.ai.yml` (in home-server-stack repo)
- Modify: `.env.example` (in home-server-stack repo)

- [x] **Step 1: Add bede-data-mcp service to docker-compose.ai.yml**

In the home-server-stack repo, add the following service to `docker-compose.ai.yml`, after the `bede-data` service:

```yaml
  bede-data-mcp:
    image: ghcr.io/josephradford/bede-data-mcp:latest
    container_name: bede-data-mcp
    restart: unless-stopped
    environment:
      - BEDE_DATA_URL=http://bede-data:8001
      - DATA_MCP_PORT=8002
    networks:
      - homeserver
    depends_on:
      bede-data:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; s=socket.create_connection(('localhost', 8002), timeout=5); s.close()"]
      interval: 30s
      timeout: 5s
      retries: 3
```

- [x] **Step 2: Verify compose config**

```bash
cd /Users/joeradford/dev/home-server-stack
make validate
```

Expected: config is valid.

- [x] **Step 3: Update CLAUDE.md architecture section**

Update the Compose File Organization section in `CLAUDE.md` to mention bede-data-mcp:

In the `docker-compose.ai.yml` line, change the description to:
```
- `docker-compose.ai.yml` — AI services (bede + bede-data + bede-data-mcp — prebuilt GHCR images from josephradford/bede)
```

- [x] **Step 4: Commit**

```bash
cd /Users/joeradford/dev/home-server-stack
git add docker-compose.ai.yml CLAUDE.md
git commit -m "feat: add bede-data-mcp service to Docker Compose"
```

- [x] **Step 5: Update CLAUDE.md.example in bede repo**

In the bede repo, update the Personal Data section of `CLAUDE.md.example` to add the new tools. After the existing tool list, add sections for:

```markdown
**Memory tools:**
- `create_memory(content, type)` -- store a new memory (fact, preference, correction, commitment)
- `list_memories(type?, search?)` -- list active memories, optionally filtered
- `update_memory(memory_id, content?, type?)` -- update a memory
- `delete_memory(memory_id)` -- soft-delete a memory
- `reference_memory(memory_id)` -- touch last-referenced timestamp for relevance ranking

**Goal tools:**
- `create_goal(name, description?, deadline?, measurable_indicators?)` -- create a new goal
- `list_goals(status?)` -- list goals (active, completed, dropped)
- `get_goal(goal_id)` -- get a single goal
- `update_goal(goal_id, ...)` -- update goal details or status

**Analytics tools:**
- `get_analytics_flags(severity?)` -- get computed wellbeing signals and trend flags
- `acknowledge_flag(flag_id)` -- mark a flag as acknowledged

**Config tools:**
- `list_schedules()` / `create_schedule(...)` / `update_schedule(...)` -- manage scheduled tasks
- `list_settings()` / `get_setting(key)` / `set_setting(key, value)` -- manage settings
- `list_monitored_items(category?)` / `create_monitored_item(...)` / `delete_monitored_item(id)` -- manage deal/news monitoring

**Data pipeline tools:**
- `get_data_freshness()` -- check when each data source last received data
- `get_storage()` -- database size and row counts

**Other tools:**
- `list_conversations()` / `get_conversation(session_id)` -- browse past conversation transcripts
- `get_task_history(task_name?)` -- scheduled task execution log
- `enqueue_vault_item(content_type, content, vault_path?)` -- queue content for vault publishing
- `get_air_quality(site_id?)` -- NSW air quality index
```

- [x] **Step 6: Commit bede repo changes**

```bash
cd /Users/joeradford/dev/bede
git add CLAUDE.md.example
git commit -m "docs: update CLAUDE.md.example with full bede-data-mcp tool inventory"
```
