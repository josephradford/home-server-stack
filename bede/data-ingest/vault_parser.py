"""Parse vault CSV-in-JSON payloads into SQLite rows.

Phase 1: log-only stub. Logs payload structure for format discovery.
"""

import logging

log = logging.getLogger(__name__)

KNOWN_FILES = {
    "screentime.csv",
    "iphone-screentime.csv",
    "safari-pages.csv",
    "iphone-safari-pages.csv",
    "youtube.csv",
    "podcasts.csv",
    "claude-sessions.md",
}


def parse_vault_payload(payload: dict) -> int:
    """Parse vault CSV payload and insert into SQLite. Returns row count.

    Phase 1 stub: logs the payload structure for format discovery.
    """
    date = payload.get("date", "unknown")
    files = payload.get("files", {})

    log.info("Vault payload received: date=%s, files=%s", date, list(files.keys()))

    for filename, content in files.items():
        if filename in KNOWN_FILES:
            lines = content.count("\n")
            log.info("  %s: %d line(s)", filename, lines)
        else:
            log.warning("  Unknown file: %s (ignored)", filename)

    # Phase 1: log only, no DB writes
    return 0
