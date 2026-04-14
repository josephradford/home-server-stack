"""Vault-based tools: reads daily-raw files from the Obsidian vault."""

import csv
import logging
import os
import subprocess
from datetime import date
from pathlib import Path

from .common import DEFAULT_TZ, resolve_date

logger = logging.getLogger(__name__)

VAULT_PATH = Path(os.environ.get("VAULT_PATH", "/vault"))
DAILY_RAW = VAULT_PATH / "data" / "daily-raw"
_VAULT_SSH_KEY = os.environ.get("VAULT_SSH_KEY_PATH", "")


def _pull_vault() -> None:
    """Pull the latest vault commits before reading. Fails silently."""
    if not (VAULT_PATH / ".git").exists():
        return
    env = os.environ.copy()
    if _VAULT_SSH_KEY and Path(_VAULT_SSH_KEY).stat().st_size > 0:
        env["GIT_SSH_COMMAND"] = f"ssh -i {_VAULT_SSH_KEY} -o StrictHostKeyChecking=no"
    result = subprocess.run(
        ["git", "-C", str(VAULT_PATH), "-c", f"safe.directory={VAULT_PATH}", "pull", "--ff-only"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        logger.warning("vault pull failed: %s", result.stderr.strip())


def _daily_dir(local_date: date) -> Path:
    return DAILY_RAW / local_date.isoformat()


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Screen time
# ---------------------------------------------------------------------------

def get_screen_time(
    date_str: str,
    device: str = "mac",
    top_n: int = 20,
    timezone: str | None = None,
) -> dict:
    """Return app and web domain usage for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        device: 'mac', 'iphone', or 'both'.
        top_n: Return only the top N entries by duration.
        timezone: Olson timezone name (default: DEFAULT_TIMEZONE env var).
    """
    _pull_vault()
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    d = _daily_dir(local_date)

    sources: list[tuple[str, str]] = []
    if device in ("mac", "both"):
        sources.append(("mac", "screentime.csv"))
    if device in ("iphone", "both"):
        sources.append(("iphone", "iphone-screentime.csv"))

    apps: list[dict] = []
    web_domains: list[dict] = []

    for dev_label, filename in sources:
        rows = _read_csv(d / filename)
        for row in rows:
            identifier = row.get("identifier") or row.get("app") or row.get("bundle_id") or row.get("name", "")
            try:
                seconds = int(float(row.get("seconds", row.get("duration", 0))))
            except (ValueError, TypeError):
                seconds = 0

            if row.get("type") == "web" or "domain" in row:
                web_domains.append({
                    "domain": row.get("domain", identifier),
                    "seconds": seconds,
                })
            else:
                apps.append({"name": identifier, "seconds": seconds, "device": dev_label})

    apps.sort(key=lambda x: x["seconds"], reverse=True)
    web_domains.sort(key=lambda x: x["seconds"], reverse=True)

    return {
        "date": local_date.isoformat(),
        "device": device,
        "apps": apps[:top_n],
        "web_domains": web_domains[:top_n],
    }


# ---------------------------------------------------------------------------
# Safari history
# ---------------------------------------------------------------------------

def get_safari_history(
    date_str: str,
    device: str = "both",
    domain_filter: str | None = None,
    top_n: int = 50,
    timezone: str | None = None,
) -> list[dict]:
    """Return Safari page visits for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        device: 'mac', 'iphone', or 'both'.
        domain_filter: Optional domain substring to filter by (e.g. 'youtube.com').
        top_n: Limit results.
        timezone: Olson timezone name.
    """
    _pull_vault()
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    d = _daily_dir(local_date)

    sources: list[tuple[str, str]] = []
    if device in ("mac", "both"):
        sources.append(("mac", "safari-pages.csv"))
    if device in ("iphone", "both"):
        sources.append(("iphone", "iphone-safari-pages.csv"))

    results: list[dict] = []
    for dev_label, filename in sources:
        rows = _read_csv(d / filename)
        for row in rows:
            domain = row.get("domain", "")
            if domain_filter and domain_filter not in domain:
                continue
            results.append({
                "visited_at": row.get("visited_at", ""),
                "domain": domain,
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "device": dev_label,
            })

    return results[:top_n]


# ---------------------------------------------------------------------------
# YouTube history (convenience wrapper)
# ---------------------------------------------------------------------------

def get_youtube_history(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return YouTube page visits for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    _pull_vault()
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    d = _daily_dir(local_date)

    rows = _read_csv(d / "youtube.csv")
    results = []
    for row in rows:
        results.append({
            "visited_at": row.get("visited_at", ""),
            "title": row.get("title", ""),
            "url": row.get("url", ""),
        })

    # Fall back to safari-pages filtered to YouTube if youtube.csv is absent
    if not rows:
        safari = get_safari_history(date_str, device="both", domain_filter="youtube.com", timezone=tz)
        results = [{"visited_at": r["visited_at"], "title": r["title"], "url": r["url"]} for r in safari]

    return results


# ---------------------------------------------------------------------------
# Podcasts
# ---------------------------------------------------------------------------

def get_podcasts(
    date_str: str,
    timezone: str | None = None,
) -> list[dict]:
    """Return podcast episodes played on a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    _pull_vault()
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    d = _daily_dir(local_date)

    rows = _read_csv(d / "podcasts.csv")
    results = []
    for row in rows:
        try:
            seconds = int(float(row.get("duration_seconds", row.get("duration", 0))))
        except (ValueError, TypeError):
            seconds = 0
        results.append({
            "episode": row.get("episode", row.get("title", "")),
            "podcast": row.get("podcast", row.get("show", "")),
            "duration_minutes": round(seconds / 60, 1),
            "played_at": row.get("played_at", ""),
        })

    return results


# ---------------------------------------------------------------------------
# Vault changes
# ---------------------------------------------------------------------------

def get_vault_changes(
    date_str: str,
    timezone: str | None = None,
) -> dict:
    """Return a summary of Obsidian vault commits for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    _pull_vault()
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    d = _daily_dir(local_date)

    txt_path = d / "vault-changes.txt"
    if not txt_path.exists():
        return {"date": local_date.isoformat(), "commits": []}

    import re
    commits: list[dict] = []
    current: dict | None = None

    # Format: "<hash>  <datetime+tz>  <message>\n\nfile1\nfile2\n\n<hash> ..."
    # File lines may be prefixed with "N. " (e.g. "1. Journal/2026-04-12.md")
    header_re = re.compile(r'^([0-9a-f]{7,})\s{2}(\S+\s+\S+)\s{2}(.+)$')

    for line in txt_path.read_text(encoding="utf-8").splitlines():
        m = header_re.match(line)
        if m:
            if current:
                commits.append(current)
            current = {"hash": m.group(1), "time": m.group(2), "message": m.group(3), "files": []}
        elif current is not None and line.strip():
            # Strip leading "N. " numbering if present
            fname = re.sub(r'^\d+\.\s+', '', line.strip())
            if fname:
                current["files"].append(fname)

    if current:
        commits.append(current)

    return {"date": local_date.isoformat(), "commits": commits}


# ---------------------------------------------------------------------------
# Claude sessions
# ---------------------------------------------------------------------------

def get_claude_sessions(
    date_str: str,
    timezone: str | None = None,
) -> str:
    """Return pre-generated Claude Code session summaries for a given local date.

    Args:
        date_str: Local date ('YYYY-MM-DD', 'today', or 'yesterday').
        timezone: Olson timezone name.
    """
    _pull_vault()
    tz = timezone or DEFAULT_TZ
    local_date = resolve_date(date_str, tz)
    d = _daily_dir(local_date)

    md_path = d / "claude-sessions.md"
    if not md_path.exists():
        return f"No Claude session data found for {local_date.isoformat()}."

    return md_path.read_text(encoding="utf-8")
