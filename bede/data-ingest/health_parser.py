"""Parse Health Auto Export JSON payloads into SQLite rows.

Phase 1: log-only stub. Logs raw payload for format discovery.
"""

import logging

log = logging.getLogger(__name__)


def parse_health_payload(payload: dict) -> int:
    """Parse HAE JSON and insert into SQLite. Returns row count.

    Phase 1 stub: logs the payload structure for format discovery.
    """
    data = payload.get("data", {})
    metrics = data.get("metrics", [])
    workouts = data.get("workouts", [])

    log.info(
        "Health payload received: %d metric(s), %d workout(s)",
        len(metrics),
        len(workouts),
    )

    # Log metric names for format discovery
    for m in metrics:
        name = m.get("name", "unknown")
        datapoints = len(m.get("data", []))
        sleep = len(m.get("aggregatedSleepAnalyses", []))
        log.info("  metric=%s datapoints=%d sleep_analyses=%d", name, datapoints, sleep)

    for w in workouts:
        log.info("  workout=%s", w.get("name", "unknown"))

    # Phase 1: log only, no DB writes
    return 0
