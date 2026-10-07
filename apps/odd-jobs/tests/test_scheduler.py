import threading
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from oddjobs.core.scheduler import Scheduler, seconds_until_next_run
from oddjobs.core.state import State
from oddjobs.jobs import JobContext, JobResult

SYDNEY = ZoneInfo("Australia/Sydney")


def test_next_run_later_today():
    now = datetime(2026, 10, 7, 1, 0, tzinfo=SYDNEY)
    assert seconds_until_next_run(now, time(4, 0)) == 3 * 3600


def test_next_run_rolls_to_tomorrow_when_time_has_passed():
    now = datetime(2026, 10, 7, 5, 0, tzinfo=SYDNEY)
    assert seconds_until_next_run(now, time(4, 0)) == 23 * 3600


def test_next_run_exactly_now_waits_a_full_day():
    now = datetime(2026, 10, 7, 4, 0, tzinfo=SYDNEY)
    assert seconds_until_next_run(now, time(4, 0)) == 24 * 3600


def test_next_run_across_dst_change_uses_wall_clock():
    # DST starts 04 Oct 2026 at 02:00 -> 03:00; 4am on the 4th is 23h after 4am on the 3rd... minus the hour.
    now = datetime(2026, 10, 3, 5, 0, tzinfo=SYDNEY)
    delta = seconds_until_next_run(now, time(4, 0))
    assert 22 * 3600 <= delta <= 24 * 3600


class FakeJob:
    name = "fake"
    run_at = time(4, 0)

    def __init__(self, action):
        self.action = action

    def run(self, ctx):
        return self.action()


def make_scheduler(tmp_path, job):
    ctx = JobContext(Path("c"), tmp_path, "d", httpx.Client())
    state = State(tmp_path / "s.db")
    return Scheduler([job], ctx, state, SYDNEY), state


def test_run_job_records_success(tmp_path):
    scheduler, state = make_scheduler(tmp_path, FakeJob(lambda: JobResult("2 fixtures")))
    assert scheduler.run_job("fake") is True
    rec = state.get("fake")
    assert rec.ok and rec.detail == "2 fixtures"


def test_run_job_records_failure_without_raising(tmp_path):
    def boom():
        raise RuntimeError("source changed")

    scheduler, state = make_scheduler(tmp_path, FakeJob(boom))
    assert scheduler.run_job("fake") is True
    rec = state.get("fake")
    assert not rec.ok and "RuntimeError: source changed" in rec.detail


def test_overlapping_run_is_refused(tmp_path):
    started, release = threading.Event(), threading.Event()

    def slow():
        started.set()
        release.wait(5)
        return JobResult("done")

    scheduler, _ = make_scheduler(tmp_path, FakeJob(slow))
    worker = threading.Thread(target=scheduler.run_job, args=("fake",))
    worker.start()
    assert started.wait(5)
    assert scheduler.run_job("fake") is False
    release.set()
    worker.join(5)
