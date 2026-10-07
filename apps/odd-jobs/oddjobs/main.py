"""Process entrypoint: wires settings, jobs, scheduler and the HTTP app."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import time
from pathlib import Path

from oddjobs.adapters.http import make_client
from oddjobs.config import load_config
from oddjobs.core.scheduler import Scheduler
from oddjobs.core.server import build_app
from oddjobs.core.state import State
from oddjobs.jobs import JobContext
from oddjobs.jobs.calendars import CalendarsJob


def create_app():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    data_dir = Path(os.environ.get("ODD_JOBS_DATA", "/data"))
    config_path = Path(os.environ.get("ODD_JOBS_CONFIG", "/config/calendars.yaml"))
    domain = os.environ.get("DOMAIN", "localhost")
    hour, minute = os.environ.get("ODD_JOBS_RUN_AT", "04:00").split(":")

    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir = data_dir / "out"
    state = State(data_dir / "state.db")
    ctx = JobContext(
        config_path=config_path, out_dir=out_dir, uid_domain=f"jobs.{domain}", client=make_client()
    )
    # The scheduler needs the timezone for "04:00 local"; fall back to the server default.
    try:
        tz = load_config(config_path).tz
    except Exception:  # noqa: BLE001 - a bad config is reported by the job run, not at boot
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Australia/Sydney")
    scheduler = Scheduler([CalendarsJob(run_at=time(int(hour), int(minute)))], ctx, state, tz)

    @asynccontextmanager
    async def lifespan(_):
        tasks = scheduler.start()
        yield
        for task in tasks:
            task.cancel()

    return build_app(scheduler, state, out_dir, lifespan=lifespan)


