"""Source-agnostic fixture model shared by every adapter and the ICS builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from enum import Enum


class Status(str, Enum):
    SCHEDULED = "scheduled"
    POSTPONED = "postponed"
    ABANDONED = "abandoned"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Day:
    """One played day. `start` is a naive local clock time in the configured timezone."""

    date: date
    start: time


@dataclass(frozen=True)
class Fixture:
    source_id: str
    title: str
    days: tuple[Day, ...]
    status: Status = Status.SCHEDULED
    venue: str | None = None
    description: str | None = None
    url: str | None = None
