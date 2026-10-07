"""The sports-calendars job: config -> adapters -> .ics files."""
from __future__ import annotations

import os
from datetime import time, timedelta
from pathlib import Path

import httpx

from oddjobs.adapters import cricket_com_au, playhq
from oddjobs.config import CalendarConfig, Config, load_config
from oddjobs.core.errors import AdapterError, OddJobsError
from oddjobs.ics_builder import build_calendar
from oddjobs.jobs import JobContext, JobResult
from oddjobs.models import Fixture


class CalendarsJob:
    name = "calendars"

    def __init__(self, run_at: time = time(4, 0)):
        self.run_at = run_at

    def run(self, ctx: JobContext) -> JobResult:
        config = load_config(ctx.config_path)
        ctx.out_dir.mkdir(parents=True, exist_ok=True)
        summaries: list[str] = []
        failures: list[str] = []
        for calendar in config.calendars:
            try:
                count = self._refresh(calendar, config, ctx)
                summaries.append(f"{calendar.name}: {count} fixtures")
            except Exception as e:  # noqa: BLE001 - one broken calendar must not stop the others
                failures.append(f"{calendar.name}: {e}")
        if failures:
            raise OddJobsError("; ".join(failures))
        return JobResult(detail=", ".join(summaries))

    def _refresh(self, calendar: CalendarConfig, config: Config, ctx: JobContext) -> int:
        fixtures = fetch_calendar(calendar, config, ctx.client)
        target = ctx.out_dir / f"{calendar.name}.ics"
        if not fixtures and _has_events(target):
            raise AdapterError("source returned zero fixtures but the previous calendar had events")
        data = build_calendar(
            calendar_name=calendar.name,
            title=calendar.title,
            fixtures=fixtures,
            tz=config.tz,
            duration=timedelta(hours=calendar.duration_hours),
            uid_domain=ctx.uid_domain,
        )
        _write_atomic(target, data)
        return len(fixtures)


def fetch_calendar(calendar: CalendarConfig, config: Config, client: httpx.Client) -> list[Fixture]:
    if calendar.source == "cricket_com_au":
        return cricket_com_au.fetch_fixtures(
            client, series=calendar.series, team=calendar.team, tz=config.tz, discover=calendar.discover,
            game_types=calendar.game_types,
        )
    return playhq.fetch_fixtures(
        client, team_id=calendar.team_id, team=calendar.team, url=calendar.url
    )


def _has_events(path: Path) -> bool:
    try:
        return b"BEGIN:VEVENT" in path.read_bytes()
    except FileNotFoundError:
        return False


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(".ics.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
