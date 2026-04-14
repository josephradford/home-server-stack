"""Tests for sources/common.py — timezone math and date resolution."""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

# Allow importing sources/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.common import (
    fmt_datetime,
    fmt_time,
    local_date_to_utc_range,
    parse_utc_iso,
    resolve_date,
)

SYDNEY = "Australia/Sydney"
UTC = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# resolve_date
# ---------------------------------------------------------------------------

class TestResolveDate:
    def test_iso_string(self):
        assert resolve_date("2026-04-14", SYDNEY) == date(2026, 4, 14)

    def test_today(self, monkeypatch):
        fixed = datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo(SYDNEY))
        monkeypatch.setattr(
            "sources.common.datetime",
            type("_dt", (), {"now": staticmethod(lambda tz: fixed), "fromisoformat": datetime.fromisoformat})(),
        )
        assert resolve_date("today", SYDNEY) == date(2026, 4, 14)

    def test_yesterday(self, monkeypatch):
        fixed = datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo(SYDNEY))
        monkeypatch.setattr(
            "sources.common.datetime",
            type("_dt", (), {"now": staticmethod(lambda tz: fixed), "fromisoformat": datetime.fromisoformat})(),
        )
        assert resolve_date("yesterday", SYDNEY) == date(2026, 4, 13)

    def test_last_night_same_as_today(self, monkeypatch):
        fixed = datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo(SYDNEY))
        monkeypatch.setattr(
            "sources.common.datetime",
            type("_dt", (), {"now": staticmethod(lambda tz: fixed), "fromisoformat": datetime.fromisoformat})(),
        )
        assert resolve_date("last_night", SYDNEY) == date(2026, 4, 14)

    def test_invalid_iso_raises(self):
        with pytest.raises(ValueError):
            resolve_date("not-a-date", SYDNEY)


# ---------------------------------------------------------------------------
# local_date_to_utc_range
# ---------------------------------------------------------------------------

class TestLocalDateToUtcRange:
    def test_aest_offset(self):
        # AEST = UTC+10; April 14 is after DST ends (AEDT → AEST), so +10
        d = date(2026, 4, 14)
        start, end = local_date_to_utc_range(d, SYDNEY)

        assert start == datetime(2026, 4, 13, 14, 0, tzinfo=UTC)
        assert end == datetime(2026, 4, 14, 14, 0, tzinfo=UTC)

    def test_aedt_offset(self):
        # AEDT = UTC+11; January is in summer (DST active)
        d = date(2026, 1, 15)
        start, end = local_date_to_utc_range(d, SYDNEY)

        assert start == datetime(2026, 1, 14, 13, 0, tzinfo=UTC)
        assert end == datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    def test_range_spans_exactly_24_local_hours(self):
        d = date(2026, 6, 21)  # AEST, no DST
        start, end = local_date_to_utc_range(d, SYDNEY)
        assert (end - start) == timedelta(hours=24)

    def test_dst_transition_day_aest_2026(self):
        # DST ends first Sunday of April 2026 = April 5
        # Clocks fall back 1 hour at 3am → 2am: the day is 25 local hours long.
        # Midnight AEDT (start) = UTC+11 → 13:00 UTC previous day
        # Midnight AEST (end)   = UTC+10 → 14:00 UTC this day
        # So the UTC span is 25 hours, not 24 — this is correct behaviour.
        d = date(2026, 4, 5)
        start, end = local_date_to_utc_range(d, SYDNEY)
        assert start == datetime(2026, 4, 4, 13, 0, tzinfo=UTC)
        assert end == datetime(2026, 4, 5, 14, 0, tzinfo=UTC)
        assert (end - start) == timedelta(hours=25)

    def test_start_before_end(self):
        for d in [date(2026, 1, 1), date(2026, 7, 1), date(2026, 4, 5)]:
            start, end = local_date_to_utc_range(d, SYDNEY)
            assert start < end

    def test_result_is_utc(self):
        d = date(2026, 4, 14)
        start, end = local_date_to_utc_range(d, SYDNEY)
        assert start.tzinfo == UTC
        assert end.tzinfo == UTC


# ---------------------------------------------------------------------------
# fmt_time
# ---------------------------------------------------------------------------

class TestFmtTime:
    def test_unix_timestamp(self):
        # 2026-04-14 00:00:00 UTC = 2026-04-14 10:00:00 AEST
        ts = datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC).timestamp()
        assert fmt_time(ts, SYDNEY) == "10:00"

    def test_datetime_object(self):
        dt = datetime(2026, 4, 14, 0, 30, tzinfo=UTC)
        assert fmt_time(dt, SYDNEY) == "10:30"

    def test_aedt_offset(self):
        # 2026-01-15 00:00:00 UTC = 2026-01-15 11:00:00 AEDT
        ts = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC).timestamp()
        assert fmt_time(ts, SYDNEY) == "11:00"


# ---------------------------------------------------------------------------
# fmt_datetime
# ---------------------------------------------------------------------------

class TestFmtDatetime:
    def test_returns_local_iso(self):
        dt = datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC)
        result = fmt_datetime(dt, SYDNEY)
        assert result.startswith("2026-04-14T10:00:00")

    def test_unix_timestamp_input(self):
        ts = datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC).timestamp()
        result = fmt_datetime(ts, SYDNEY)
        assert result.startswith("2026-04-14T10:00:00")


# ---------------------------------------------------------------------------
# parse_utc_iso
# ---------------------------------------------------------------------------

class TestParseUtcIso:
    def test_z_suffix(self):
        dt = parse_utc_iso("2026-04-14T00:00:00Z")
        assert dt == datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC)

    def test_plus_zero_offset(self):
        dt = parse_utc_iso("2026-04-14T00:00:00+00:00")
        assert dt == datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC)

    def test_no_suffix(self):
        dt = parse_utc_iso("2026-04-14T12:30:00")
        assert dt == datetime(2026, 4, 14, 12, 30, 0, tzinfo=UTC)

    def test_space_separator(self):
        dt = parse_utc_iso("2026-04-14 06:00:00")
        assert dt == datetime(2026, 4, 14, 6, 0, 0, tzinfo=UTC)
