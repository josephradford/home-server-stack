import httpx

from oddjobs.probe import main, probe
from tests.test_calendars_job import CONFIG, healthy


def write_config(tmp_path):
    path = tmp_path / "calendars.yaml"
    path.write_text(CONFIG)
    return path


def test_probe_reports_each_calendar(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(healthy)) as client:
        lines, ok = probe(write_config(tmp_path), client)
    assert ok
    assert lines[0].startswith("ok   australia-tests: 1 fixtures, 2026-12-09")
    assert lines[1].startswith("ok   parramatta-first-grade: 1 fixtures, 2026-10-10")


def test_probe_flags_failures_and_empty_sources(tmp_path):
    def broken(request):
        if "cricket.com.au" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, json={"data": {"discoverTeamFixture": []}})

    with httpx.Client(transport=httpx.MockTransport(broken)) as client:
        lines, ok = probe(write_config(tmp_path), client)
    assert not ok
    assert lines[0].startswith("FAIL australia-tests")
    assert lines[1] == "FAIL parramatta-first-grade: source returned zero fixtures"


def test_main_usage_and_bad_config(tmp_path, capsys):
    assert main(["probe"]) == 2
    assert main(["probe", str(tmp_path / "missing.yaml")]) == 1
    assert "FAIL config" in capsys.readouterr().out
