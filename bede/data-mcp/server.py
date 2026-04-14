"""Bede Data MCP — FastMCP server exposing personal data tools."""

from fastmcp import FastMCP

from sources import health, location, vault

mcp = FastMCP("personal-data")


# ---------------------------------------------------------------------------
# Vault-based tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_screen_time(
    date: str,
    device: str = "mac",
    top_n: int = 20,
    timezone: str | None = None,
) -> dict:
    """Return app and web domain screen time usage for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        device: 'mac', 'iphone', or 'both'.
        top_n: Return only the top N entries by duration.
        timezone: Olson timezone name (default: Australia/Sydney).
    """
    return vault.get_screen_time(date, device=device, top_n=top_n, timezone=timezone)


@mcp.tool()
def get_safari_history(
    date: str,
    device: str = "both",
    domain_filter: str | None = None,
    top_n: int = 50,
    timezone: str | None = None,
) -> list[dict]:
    """Return Safari page visits for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        device: 'mac', 'iphone', or 'both'.
        domain_filter: Optional domain substring to filter by (e.g. 'github.com').
        top_n: Limit number of results.
        timezone: Olson timezone name.
    """
    return vault.get_safari_history(
        date, device=device, domain_filter=domain_filter, top_n=top_n, timezone=timezone
    )


@mcp.tool()
def get_youtube_history(
    date: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return YouTube page visits for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return vault.get_youtube_history(date, timezone=timezone)


@mcp.tool()
def get_podcasts(
    date: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return podcast episodes played on a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return vault.get_podcasts(date, timezone=timezone)


@mcp.tool()
def get_vault_changes(
    date: str,
    timezone: str | None = None,
) -> dict:
    """Return a summary of Obsidian vault git commits for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return vault.get_vault_changes(date, timezone=timezone)


@mcp.tool()
def get_claude_sessions(
    date: str,
    timezone: str | None = None,
) -> str:
    """Return pre-generated Claude Code session summaries for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return vault.get_claude_sessions(date, timezone=timezone)


# ---------------------------------------------------------------------------
# Live API tools — location
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_location_summary(
    date: str,
    timezone: str | None = None,
) -> dict:
    """Return summarised stops for a given local date.

    Clusters GPS points into stops by proximity, reverse-geocodes each stop
    via Nominatim, and returns local timestamps. All UTC conversion is done
    internally — never pass UTC dates to this tool.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name (default: Australia/Sydney).
    """
    return await location.get_location_summary(date, timezone=timezone)


@mcp.tool()
async def get_location_raw(
    from_date: str,
    to_date: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return raw GPS points for a local date range without summarisation.

    Args:
        from_date: Start local date ('YYYY-MM-DD').
        to_date: End local date ('YYYY-MM-DD').
        timezone: Olson timezone name.
    """
    return await location.get_location_raw(from_date, to_date, timezone=timezone)


# ---------------------------------------------------------------------------
# Live API tools — health
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_sleep(
    date: str,
    timezone: str | None = None,
) -> dict:
    """Return sleep summary for the night ending on the given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'last_night'.
        timezone: Olson timezone name.
    """
    return await health.get_sleep(date, timezone=timezone)


@mcp.tool()
async def get_activity(
    date: str,
    timezone: str | None = None,
) -> dict:
    """Return daily activity summary (steps, calories, exercise, stand).

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await health.get_activity(date, timezone=timezone)


@mcp.tool()
async def get_workouts(
    date: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return workouts recorded on a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await health.get_workouts(date, timezone=timezone)


@mcp.tool()
async def get_heart_rate(
    date: str,
    timezone: str | None = None,
) -> dict:
    """Return resting heart rate and HRV for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await health.get_heart_rate(date, timezone=timezone)


@mcp.tool()
async def get_wellbeing(
    date: str,
    timezone: str | None = None,
) -> dict:
    """Return mindfulness duration and state of mind entries for a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await health.get_wellbeing(date, timezone=timezone)


@mcp.tool()
async def get_medications(
    date: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return medications logged on a given local date.

    Args:
        date: Local date — 'YYYY-MM-DD', 'today', or 'yesterday'.
        timezone: Olson timezone name.
    """
    return await health.get_medications(date, timezone=timezone)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
