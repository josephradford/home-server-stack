"""Tests for health_parser — HAE JSON payload parsing."""

import pytest

from db import get_db
from health_parser import _parse_hae_timestamp, parse_health_payload


class TestParseHaeTimestamp:
    def test_hae_format_with_positive_offset(self):
        result = _parse_hae_timestamp("2026-04-14 06:00:00 +1000")
        assert result == ("2026-04-14", "2026-04-13T20:00:00Z")

    def test_hae_format_with_negative_offset(self):
        result = _parse_hae_timestamp("2026-04-14 06:00:00 -0500")
        assert result == ("2026-04-14", "2026-04-14T11:00:00Z")

    def test_iso8601_format(self):
        result = _parse_hae_timestamp("2026-04-14T06:00:00+10:00")
        assert result == ("2026-04-14", "2026-04-13T20:00:00Z")

    def test_utc_z_suffix(self):
        result = _parse_hae_timestamp("2026-04-14T06:00:00+00:00")
        assert result == ("2026-04-14", "2026-04-14T06:00:00Z")

    def test_empty_returns_none(self):
        assert _parse_hae_timestamp("") is None

    def test_invalid_returns_none(self):
        assert _parse_hae_timestamp("not-a-date") is None


class TestGenericMetrics:
    def test_step_count(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "step_count",
                        "units": "count",
                        "data": [
                            {"date": "2026-04-14 06:00:00 +1000", "qty": 8423, "source": "iPhone"},
                            {"date": "2026-04-14 12:00:00 +1000", "qty": 3200, "source": "Apple Watch"},
                        ],
                    }
                ],
                "workouts": [],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 2

        db = get_db()
        results = db.execute("SELECT * FROM health_metrics WHERE metric = 'step_count' ORDER BY recorded_at").fetchall()
        assert len(results) == 2
        assert results[0]["value"] == 8423
        assert results[0]["source"] == "iPhone"
        assert results[1]["value"] == 3200
        assert results[1]["source"] == "Apple Watch"

    def test_active_energy(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "active_energy",
                        "units": "kJ",
                        "data": [{"date": "2026-04-14 06:00:00 +1000", "qty": 1250.5}],
                    }
                ],
                "workouts": [],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM health_metrics WHERE metric = 'active_energy_kJ'").fetchone()
        assert row["value"] == 1250.5

    def test_idempotent_insert(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "step_count",
                        "units": "count",
                        "data": [{"date": "2026-04-14 06:00:00 +1000", "qty": 8423, "source": "iPhone"}],
                    }
                ],
                "workouts": [],
            }
        }
        parse_health_payload(payload)
        parse_health_payload(payload)  # second time should be idempotent

        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM health_metrics").fetchone()[0]
        assert count == 1

    def test_metric_with_units_already_in_name(self):
        """If units are already part of the name, don't duplicate them."""
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "active_energy_kJ",
                        "units": "kJ",
                        "data": [{"date": "2026-04-14 06:00:00 +1000", "qty": 500}],
                    }
                ],
                "workouts": [],
            }
        }
        parse_health_payload(payload)
        db = get_db()
        row = db.execute("SELECT metric FROM health_metrics").fetchone()
        assert row["metric"] == "active_energy_kJ"  # not "active_energy_kJ_kJ"

    def test_skip_null_qty(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "step_count",
                        "units": "count",
                        "data": [{"date": "2026-04-14 06:00:00 +1000", "qty": None}],
                    }
                ],
                "workouts": [],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 0


class TestSleep:
    def test_aggregated_sleep(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "sleep_analysis",
                        "aggregatedSleepAnalyses": [
                            {
                                "sleepStart": "2026-04-13 22:30:00 +1000",
                                "sleepEnd": "2026-04-14 06:30:00 +1000",
                                "core": 3.5,
                                "deep": 1.2,
                                "rem": 2.1,
                                "awake": 0.7,
                                "source": "Apple Watch",
                            }
                        ],
                    }
                ],
                "workouts": [],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 4  # core, deep, rem, awake

        db = get_db()
        phases = db.execute("SELECT * FROM sleep_phases WHERE date = '2026-04-14' ORDER BY stage").fetchall()
        stages = {p["stage"]: p["hours"] for p in phases}
        assert stages["core"] == 3.5
        assert stages["deep"] == 1.2
        assert stages["rem"] == 2.1
        assert stages["awake"] == 0.7
        assert phases[0]["source"] == "Apple Watch"
        assert phases[0]["sleep_start"] is not None
        assert phases[0]["sleep_end"] is not None

    def test_sleep_uses_wake_date(self):
        """Sleep that starts on the 13th and ends on the 14th should use the 14th as the date."""
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "sleep_analysis",
                        "aggregatedSleepAnalyses": [
                            {
                                "sleepStart": "2026-04-13 23:00:00 +1000",
                                "sleepEnd": "2026-04-14 07:00:00 +1000",
                                "deep": 2.0,
                            }
                        ],
                    }
                ],
                "workouts": [],
            }
        }
        parse_health_payload(payload)
        db = get_db()
        row = db.execute("SELECT date FROM sleep_phases").fetchone()
        assert row["date"] == "2026-04-14"


class TestWorkouts:
    def test_basic_workout(self):
        payload = {
            "data": {
                "metrics": [],
                "workouts": [
                    {
                        "name": "Running",
                        "start": "2026-04-14 06:30:00 +1000",
                        "end": "2026-04-14 07:00:00 +1000",
                        "duration": 1800,
                        "activeEnergy": 850.5,
                        "avgHeartRate": 155,
                        "maxHeartRate": 178,
                    }
                ],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 1

        db = get_db()
        w = db.execute("SELECT * FROM workouts").fetchone()
        assert w["workout_name"] == "Running"
        assert w["duration_min"] == 30.0
        assert w["active_energy_kj"] == 850.5
        assert w["avg_heart_rate_bpm"] == 155
        assert w["max_heart_rate_bpm"] == 178
        assert w["date"] == "2026-04-14"

    def test_workout_without_optional_fields(self):
        payload = {
            "data": {
                "metrics": [],
                "workouts": [
                    {
                        "name": "Yoga",
                        "start": "2026-04-14 08:00:00 +1000",
                        "end": "2026-04-14 09:00:00 +1000",
                    }
                ],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 1

        db = get_db()
        w = db.execute("SELECT * FROM workouts").fetchone()
        assert w["workout_name"] == "Yoga"
        assert w["duration_min"] is None
        assert w["avg_heart_rate_bpm"] is None


class TestStateOfMind:
    def test_state_of_mind(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "state_of_mind",
                        "data": [
                            {
                                "date": "2026-04-14 09:00:00 +1000",
                                "qty": 0.8,
                                "labels": "Happy,Grateful",
                                "context": "daily",
                            }
                        ],
                    }
                ],
                "workouts": [],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM state_of_mind").fetchone()
        assert row["valence"] == 0.8
        assert "Happy" in row["labels"]
        assert row["context"] == "daily"


class TestMedications:
    def test_medication(self):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "medication_vitamin_d",
                        "units": "IU",
                        "data": [
                            {"date": "2026-04-14 08:00:00 +1000", "qty": 1000}
                        ],
                    }
                ],
                "workouts": [],
            }
        }
        rows = parse_health_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM medications").fetchone()
        assert row["name"] == "medication_vitamin_d"
        assert row["quantity"] == 1000
        assert row["unit"] == "IU"


class TestEmptyPayload:
    def test_empty_data(self):
        rows = parse_health_payload({"data": {}})
        assert rows == 0

    def test_no_data_key(self):
        rows = parse_health_payload({})
        assert rows == 0
