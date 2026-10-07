from oddjobs.core.state import State


def test_unknown_job_is_none(tmp_path):
    assert State(tmp_path / "s.db").get("calendars") is None


def test_success_then_failure_keeps_last_success_time(tmp_path):
    state = State(tmp_path / "s.db")
    state.record_success("calendars", "3 fixtures", now=100.0)
    state.record_failure("calendars", "boom", now=200.0)
    rec = state.get("calendars")
    assert (rec.ok, rec.last_run_at, rec.last_success_at, rec.detail) == (False, 200.0, 100.0, "boom")
    state.record_success("calendars", "again", now=300.0)
    rec = state.get("calendars")
    assert (rec.ok, rec.last_success_at) == (True, 300.0)


def test_state_survives_reopen(tmp_path):
    State(tmp_path / "s.db").record_success("calendars", "x", now=5.0)
    assert State(tmp_path / "s.db").get("calendars").last_success_at == 5.0
