"""Data ingest server — receives health and vault data, writes to SQLite."""

import json
import logging
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from auth import require_auth
from db import init_db
from health_parser import parse_health_payload
from vault_parser import parse_vault_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint — no auth required."""
    return JSONResponse({"status": "ok"})


async def ingest_health(request: Request) -> JSONResponse:
    """Receive HAE JSON payload from iPhone."""
    auth_error = await require_auth(request)
    if auth_error:
        return auth_error

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Log raw payload at DEBUG for format discovery
    log.debug("Raw health payload: %s", json.dumps(payload)[:2000])

    rows = parse_health_payload(payload)
    return JSONResponse({"status": "ok", "rows_inserted": rows})


async def ingest_vault(request: Request) -> JSONResponse:
    """Receive vault CSV-in-JSON payload from Mac nightly job."""
    auth_error = await require_auth(request)
    if auth_error:
        return auth_error

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if "date" not in payload:
        return JSONResponse({"error": "Missing 'date' field"}, status_code=400)

    rows = parse_vault_payload(payload)
    return JSONResponse({"status": "ok", "rows_inserted": rows})


routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/ingest/health", ingest_health, methods=["POST"]),
    Route("/ingest/vault", ingest_vault, methods=["POST"]),
]

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = Starlette(routes=routes, lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
