"""Bearer token authentication for ingest endpoints."""

import os

from starlette.requests import Request
from starlette.responses import JSONResponse

INGEST_WRITE_TOKEN = os.environ.get("INGEST_WRITE_TOKEN", "")


async def require_auth(request: Request) -> JSONResponse | None:
    """Check Bearer token. Returns a 401 response on failure, None on success."""
    if not INGEST_WRITE_TOKEN:
        return JSONResponse({"error": "INGEST_WRITE_TOKEN not configured"}, status_code=500)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != INGEST_WRITE_TOKEN:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return None
