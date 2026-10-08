"""Runs each job once at startup and then daily at its configured local time."""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from oddjobs.core.state import State
from oddjobs.jobs import Job, JobContext

log = logging.getLogger("oddjobs.scheduler")


def seconds_until_next_run(now: datetime, at: time) -> float:
    """Seconds from `now` (timezone-aware) until the next local wall-clock `at`."""
    target = datetime.combine(now.date(), at, tzinfo=now.tzinfo)
    if target <= now:
        target = datetime.combine(now.date() + timedelta(days=1), at, tzinfo=now.tzinfo)
    return (target - now).total_seconds()


class Scheduler:
    def __init__(self, jobs: list[Job], ctx: JobContext, state: State, tz: ZoneInfo):
        self.jobs = {job.name: job for job in jobs}
        self._ctx = ctx
        self._state = state
        self._tz = tz
        self._lock = threading.Lock()  # jobs never overlap, including manual runs

    def run_job(self, name: str, wait: bool = False) -> bool:
        """Run a job now. Unless `wait`, returns False if another run is in progress."""
        if not self._lock.acquire(blocking=wait):
            return False
        try:
            job = self.jobs[name]
            try:
                result = job.run(self._ctx)
            except Exception as e:  # noqa: BLE001 - any failure must be recorded, not crash the loop
                log.exception("job %s failed", name)
                self._state.record_failure(name, f"{type(e).__name__}: {e}")
            else:
                log.info("job %s ok: %s", name, result.detail)
                self._state.record_success(name, result.detail)
            return True
        finally:
            self._lock.release()

    async def _loop(self, job: Job) -> None:
        await asyncio.to_thread(self.run_job, job.name, True)
        while True:
            await asyncio.sleep(seconds_until_next_run(datetime.now(self._tz), job.run_at))
            await asyncio.to_thread(self.run_job, job.name, True)

    def start(self) -> list[asyncio.Task]:
        return [asyncio.create_task(self._loop(job)) for job in self.jobs.values()]
