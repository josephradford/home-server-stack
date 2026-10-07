from starlette.testclient import TestClient

from oddjobs.main import create_app
from tests.test_calendars_job import CONFIG


def test_create_app_wires_settings_from_environment(tmp_path, monkeypatch):
    config = tmp_path / "calendars.yaml"
    config.write_text(CONFIG)
    monkeypatch.setenv("ODD_JOBS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("ODD_JOBS_CONFIG", str(config))
    monkeypatch.setenv("DOMAIN", "example.com")
    monkeypatch.setenv("ODD_JOBS_RUN_AT", "05:30")

    # No `with` block: the lifespan (and so the live-network first run) is not started.
    client = TestClient(create_app())
    assert client.get("/healthz").text == "ok"
    assert "calendars" in client.get("/").text
    assert client.get("/australia-tests.ics").status_code == 404  # nothing has run yet
    assert (tmp_path / "data" / "state.db").exists()


def test_create_app_survives_a_bad_config_so_the_status_page_can_report_it(tmp_path, monkeypatch):
    monkeypatch.setenv("ODD_JOBS_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("ODD_JOBS_CONFIG", str(tmp_path / "missing.yaml"))
    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
