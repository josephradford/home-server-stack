"""Live check of every configured source: `python -m oddjobs.probe /config/calendars.yaml`.

Fetches each calendar once, prints what was found, and exits non-zero if any source
fails to parse. Writes nothing. Use it after a suspected source change.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

from oddjobs.adapters.http import make_client
from oddjobs.config import load_config
from oddjobs.core.errors import OddJobsError
from oddjobs.jobs.calendars import fetch_calendar


def probe(config_path: Path, client: httpx.Client) -> tuple[list[str], bool]:
    config = load_config(config_path)
    lines: list[str] = []
    ok = True
    for calendar in config.calendars:
        try:
            fixtures = fetch_calendar(calendar, config, client)
        except OddJobsError as e:
            lines.append(f"FAIL {calendar.name}: {e}")
            ok = False
            continue
        if not fixtures:
            lines.append(f"FAIL {calendar.name}: source returned zero fixtures")
            ok = False
            continue
        first = min(fixtures, key=lambda f: f.days[0].date)
        last = max(fixtures, key=lambda f: f.days[0].date)
        lines.append(
            f"ok   {calendar.name}: {len(fixtures)} fixtures, "
            f"{first.days[0].date} ({first.title}) .. {last.days[0].date} ({last.title})"
        )
    return lines, ok


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m oddjobs.probe <calendars.yaml>", file=sys.stderr)
        return 2
    with make_client() as client:
        try:
            lines, ok = probe(Path(argv[1]), client)
        except OddJobsError as e:
            print(f"FAIL config: {e}")
            return 1
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
