"""Weather data via homepage-api BOM endpoint."""

import httpx

HOMEPAGE_API_URL = "http://homepage-api:5000"


async def get_weather() -> dict:
    """Fetch current weather and forecast from BOM via homepage-api."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HOMEPAGE_API_URL}/api/bom/weather")
        resp.raise_for_status()
        return resp.json()
