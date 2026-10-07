"""Loads and validates calendars.yaml."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from oddjobs.core.errors import ConfigError

SOURCES = ("cricket_com_au", "playhq")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class CalendarConfig:
    name: str
    title: str
    source: str
    team: str
    duration_hours: float = 6
    series: tuple[str, ...] = ()
    discover: bool = False
    game_types: tuple[str, ...] = ()
    team_id: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class Config:
    timezone: str
    calendars: tuple[CalendarConfig, ...]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_config(path: Path) -> Config:
    try:
        raw = yaml.safe_load(Path(path).read_text())
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}") from None
    if not isinstance(raw, dict):
        raise ConfigError("config must be a mapping")

    timezone = raw.get("timezone", "Australia/Sydney")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f"unknown timezone: {timezone}") from None

    entries = raw.get("calendars")
    if not isinstance(entries, list) or not entries:
        raise ConfigError("'calendars' must be a non-empty list")

    calendars: list[CalendarConfig] = []
    seen: set[str] = set()
    for entry in entries:
        calendars.append(_parse_calendar(entry, seen))
    return Config(timezone=timezone, calendars=tuple(calendars))


def _parse_calendar(entry: object, seen: set[str]) -> CalendarConfig:
    if not isinstance(entry, dict):
        raise ConfigError("each calendar must be a mapping")
    for key in ("name", "title", "source", "team"):
        if not entry.get(key):
            raise ConfigError(f"calendar missing required key '{key}': {entry}")
    name = entry["name"]
    if not _NAME_RE.match(name):
        raise ConfigError(f"calendar name must be lowercase letters, digits, dashes: {name!r}")
    if name in seen:
        raise ConfigError(f"duplicate calendar name: {name}")
    seen.add(name)
    source = entry["source"]
    if source not in SOURCES:
        raise ConfigError(f"calendar {name}: unknown source {source!r} (expected one of {SOURCES})")
    series = tuple(entry.get("series") or ())
    team_id = entry.get("team_id")
    discover = bool(entry.get("discover", False))
    if source == "cricket_com_au" and not series and not discover:
        raise ConfigError(f"calendar {name}: cricket_com_au needs a non-empty 'series' list or 'discover: true'")
    if source == "playhq" and not team_id:
        raise ConfigError(f"calendar {name}: playhq needs 'team_id'")
    return CalendarConfig(
        name=name,
        title=entry["title"],
        source=source,
        team=entry["team"],
        duration_hours=float(entry.get("duration_hours", 6)),
        series=series,
        discover=discover,
        game_types=tuple(entry.get("game_types") or ()),
        team_id=str(team_id) if team_id else None,
        url=entry.get("url"),
    )
