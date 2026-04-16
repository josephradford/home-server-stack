"""Tests for health.py — SQLite-backed health data queries."""

import pytest

from sources.health import get_sleep, get_activity, get_workouts, get_heart_rate, get_wellbeing, get_medications


class TestGetSleep:
    def test_returns_sleep_summary(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO sleep_phases (date, stage, hours, sleep_start, sleep_end, source) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "core", 3.5, "2026-04-13T12:30:00Z", "2026-04-13T20:30:00Z", "Apple Watch"),
                ("2026-04-14", "deep", 1.2, "2026-04-13T12:30:00Z", "2026-04-13T20:30:00Z", "Apple Watch"),
                ("2026-04-14", "rem", 2.1, "2026-04-13T12:30:00Z", "2026-04-13T20:30:00Z", "Apple Watch"),
                ("2026-04-14", "awake", 0.7, "2026-04-13T12:30:00Z", "2026-04-13T20:30:00Z", "Apple Watch"),
            ],
        )
        fresh_db.commit()

        result = get_sleep("2026-04-14", timezone="Australia/Sydney")
        assert result["date"] == "2026-04-14"
        assert result["duration_hours"] == 6.8  # core + deep + rem
        assert "core" in result["stages"]
        assert "deep" in result["stages"]
        assert "rem" in result["stages"]
        assert "awake" not in result["stages"]
        assert result["bedtime"] is not None
        assert result["wake_time"] is not None

    def test_no_data_returns_empty(self, fresh_db):
        result = get_sleep("2026-04-14", timezone="Australia/Sydney")
        assert result["duration_hours"] == 0
        assert result["bedtime"] is None


class TestGetActivity:
    def test_returns_activity_summary(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "step_count", 5000, "iPhone", "2026-04-13T20:00:00Z"),
                ("2026-04-14", "step_count", 3000, "Apple Watch", "2026-04-14T02:00:00Z"),
                ("2026-04-14", "active_energy_kJ", 1250.5, "Apple Watch", "2026-04-14T02:00:00Z"),
                ("2026-04-14", "apple_exercise_time_min", 45, "Apple Watch", "2026-04-14T02:00:00Z"),
                ("2026-04-14", "apple_stand_hour_count", 10, "Apple Watch", "2026-04-14T02:00:00Z"),
            ],
        )
        fresh_db.commit()

        result = get_activity("2026-04-14", timezone="Australia/Sydney")
        assert result["steps"] == 8000  # 5000 + 3000
        assert result["active_energy_kcal"] == round(1250.5 / 4.184)
        assert result["exercise_minutes"] == 45
        assert result["stand_hours"] == 10

    def test_no_data_returns_zeros(self, fresh_db):
        result = get_activity("2026-04-14", timezone="Australia/Sydney")
        assert result["steps"] == 0
        assert result["active_energy_kcal"] == 0


class TestGetWorkouts:
    def test_returns_workouts(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO workouts (date, workout_name, start_time, end_time, duration_min, active_energy_kj, avg_heart_rate_bpm, max_heart_rate_bpm) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-04-14", "Running", "2026-04-13T20:30:00Z", "2026-04-13T21:00:00Z", 30.0, 1200.5, 155, 178),
        )
        fresh_db.commit()

        result = get_workouts("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["type"] == "Running"
        assert result[0]["duration_minutes"] == 30.0
        assert result[0]["energy_kcal"] == round(1200.5 / 4.184)
        assert result[0]["start_time"] == "06:30"  # +10 hours from UTC

    def test_no_data_returns_empty(self, fresh_db):
        result = get_workouts("2026-04-14", timezone="Australia/Sydney")
        assert result == []


class TestGetHeartRate:
    def test_returns_averages(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "resting_heart_rate", 60, "Apple Watch", "2026-04-14T00:00:00Z"),
                ("2026-04-14", "resting_heart_rate", 62, "Apple Watch", "2026-04-14T06:00:00Z"),
                ("2026-04-14", "heart_rate_variability", 45, "Apple Watch", "2026-04-14T00:00:00Z"),
                ("2026-04-14", "heart_rate_variability", 55, "Apple Watch", "2026-04-14T06:00:00Z"),
            ],
        )
        fresh_db.commit()

        result = get_heart_rate("2026-04-14", timezone="Australia/Sydney")
        assert result["resting_heart_rate_bpm"] == 61  # avg(60, 62)
        assert result["hrv_ms"] == 50  # avg(45, 55)

    def test_no_data_returns_none(self, fresh_db):
        result = get_heart_rate("2026-04-14", timezone="Australia/Sydney")
        assert result["resting_heart_rate_bpm"] is None
        assert result["hrv_ms"] is None


class TestGetWellbeing:
    def test_returns_state_of_mind_and_mindful(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO health_metrics (date, metric, value, source, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-14", "mindful_minutes", 15, "iPhone", "2026-04-14T00:00:00Z"),
        )
        fresh_db.execute(
            "INSERT INTO state_of_mind (date, recorded_at, valence, labels, context) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-14", "2026-04-13T23:00:00Z", 0.8, '["Happy", "Grateful"]', "daily"),
        )
        fresh_db.commit()

        result = get_wellbeing("2026-04-14", timezone="Australia/Sydney")
        assert result["mindful_minutes"] == 15
        assert len(result["state_of_mind"]) == 1
        assert result["state_of_mind"][0]["valence"] == 0.8
        assert "Happy" in result["state_of_mind"][0]["labels"]

    def test_no_data_returns_empty(self, fresh_db):
        result = get_wellbeing("2026-04-14", timezone="Australia/Sydney")
        assert result["mindful_minutes"] is None
        assert result["state_of_mind"] == []


class TestGetMedications:
    def test_returns_medications(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO medications (date, name, quantity, unit, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-14", "Vitamin D", 1000, "IU", "2026-04-13T22:00:00Z"),
        )
        fresh_db.commit()

        result = get_medications("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["name"] == "Vitamin D"
        assert result[0]["qty"] == 1000
        assert result[0]["time"] == "08:00"  # +10 from UTC

    def test_no_data_returns_empty(self, fresh_db):
        result = get_medications("2026-04-14", timezone="Australia/Sydney")
        assert result == []
