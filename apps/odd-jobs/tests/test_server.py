from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from starlette.testclient import TestClient

from oddjobs.core.scheduler import Scheduler
from oddjobs.core.server import build_app
from oddjobs.core.state import State
from oddjobs.jobs import JobContext, JobResult


class FakeJob:
    name = "calendars"
    run_at = time(4, 0)

    def run(self, ctx):
        return JobResult("ok")


def make_client(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "nsw-shield.ics").write_bytes(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    (tmp_path / "secret.ics").write_bytes(b"secret")
    state = State(tmp_path / "s.db")
    ctx = JobContext(Path("c"), out, "d", httpx.Client())
    scheduler = Scheduler([FakeJob()], ctx, state, ZoneInfo("Australia/Sydney"))
    return TestClient(build_app(scheduler, state, out)), state


def test_serves_calendar_with_ics_content_type(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.get("/nsw-shield.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert b"BEGIN:VCALENDAR" in response.content


def test_unknown_and_traversal_paths_are_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/missing.ics").status_code == 404
    assert client.get("/..%2Fsecret.ics").status_code == 404
    assert client.get("/%2e%2e/secret.ics").status_code == 404


def test_healthz(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/healthz").text == "ok"


def test_metrics_before_and_after_a_run(tmp_path):
    client, state = make_client(tmp_path)
    before = client.get("/metrics").text
    assert 'odd_jobs_last_success_timestamp_seconds{job="calendars"} 0' in before
    assert 'odd_jobs_last_run_ok{job="calendars"} 0' in before
    state.record_success("calendars", "x", now=1234.0)
    after = client.get("/metrics").text
    assert 'odd_jobs_last_success_timestamp_seconds{job="calendars"} 1234.0' in after
    assert 'odd_jobs_last_run_ok{job="calendars"} 1' in after


def test_failed_run_reports_not_ok_but_keeps_last_success(tmp_path):
    client, state = make_client(tmp_path)
    state.record_success("calendars", "x", now=1234.0)
    state.record_failure("calendars", "boom", now=2000.0)
    text = client.get("/metrics").text
    assert 'odd_jobs_last_success_timestamp_seconds{job="calendars"} 1234.0' in text
    assert 'odd_jobs_last_run_ok{job="calendars"} 0' in text


def test_manual_run_and_unknown_job(tmp_path):
    client, state = make_client(tmp_path)
    assert client.post("/run/calendars").status_code == 200
    assert state.get("calendars").ok
    assert client.post("/run/nope").status_code == 404
    assert client.get("/run/calendars").status_code == 405


def test_status_page_lists_jobs_and_calendars_and_escapes(tmp_path):
    client, state = make_client(tmp_path)
    state.record_failure("calendars", "<script>x</script>", now=1.0)
    body = client.get("/").text
    assert "calendars" in body and "FAILED" in body and "nsw-shield.ics" in body
    assert "<script>x</script>" not in body
