import pytest

from oddjobs.config import load_config
from oddjobs.core.errors import ConfigError

VALID = """
timezone: Australia/Sydney
calendars:
  - name: australia-tests
    title: Australia Men's Tests
    source: cricket_com_au
    series: ["CA:4605"]
    team: "Australia Men"
  - name: parramatta-first-grade
    title: Parramatta First Grade
    source: playhq
    team_id: bb481fee
    team: "Parramatta First Grade"
    duration_hours: 7
    url: https://www.playhq.com/example
"""


def write(tmp_path, text):
    path = tmp_path / "calendars.yaml"
    path.write_text(text)
    return path


def test_loads_valid_config(tmp_path):
    config = load_config(write(tmp_path, VALID))
    assert config.timezone == "Australia/Sydney"
    tests, grade = config.calendars
    assert tests.series == ("CA:4605",)
    assert tests.duration_hours == 6
    assert grade.team_id == "bb481fee"
    assert grade.duration_hours == 7
    assert grade.url == "https://www.playhq.com/example"


def test_missing_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda t: t.replace("source: cricket_com_au", "source: espn"), "unknown source"),
        (lambda t: t.replace("name: australia-tests", "name: ../evil"), "calendar name"),
        (lambda t: t.replace("name: parramatta-first-grade", "name: australia-tests"), "duplicate"),
        (lambda t: t.replace('    series: ["CA:4605"]\n', ""), "series"),
        (lambda t: t.replace("    team_id: bb481fee\n", ""), "team_id"),
        (lambda t: t.replace("Australia/Sydney", "Mars/Olympus"), "timezone"),
        (lambda t: "calendars: []", "non-empty"),
        (lambda t: "- just\n- a list", "mapping"),
    ],
)
def test_invalid_configs(tmp_path, mutation, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, mutation(VALID)))
