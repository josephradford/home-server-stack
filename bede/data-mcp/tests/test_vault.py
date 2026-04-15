"""Tests for vault.py — SQLite-backed vault data queries."""

import pytest

from sources.vault import get_screen_time, get_safari_history, get_youtube_history, get_podcasts, get_claude_sessions


class TestGetScreenTime:
    def test_returns_apps_and_web(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO screen_time (date, device, entry_type, identifier, seconds) VALUES (?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "mac", "app", "com.apple.Safari", 3600),
                ("2026-04-14", "mac", "app", "com.google.Chrome", 1800),
                ("2026-04-14", "mac", "web", "github.com", 900),
            ],
        )
        fresh_db.commit()

        result = get_screen_time("2026-04-14", device="mac", timezone="Australia/Sydney")
        assert result["date"] == "2026-04-14"
        assert len(result["apps"]) == 2
        assert result["apps"][0]["name"] == "com.apple.Safari"  # sorted by seconds desc
        assert result["apps"][0]["seconds"] == 3600
        assert len(result["web_domains"]) == 1
        assert result["web_domains"][0]["domain"] == "github.com"

    def test_device_filter(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO screen_time (date, device, entry_type, identifier, seconds) VALUES (?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "mac", "app", "Safari", 3600),
                ("2026-04-14", "iphone", "app", "Instagram", 1200),
            ],
        )
        fresh_db.commit()

        mac = get_screen_time("2026-04-14", device="mac", timezone="Australia/Sydney")
        assert len(mac["apps"]) == 1
        assert mac["apps"][0]["name"] == "Safari"

        both = get_screen_time("2026-04-14", device="both", timezone="Australia/Sydney")
        assert len(both["apps"]) == 2

    def test_top_n_limit(self, fresh_db):
        for i in range(10):
            fresh_db.execute(
                "INSERT INTO screen_time (date, device, entry_type, identifier, seconds) VALUES (?, ?, ?, ?, ?)",
                ("2026-04-14", "mac", "app", f"App{i}", (10 - i) * 100),
            )
        fresh_db.commit()

        result = get_screen_time("2026-04-14", device="mac", top_n=3, timezone="Australia/Sydney")
        assert len(result["apps"]) == 3

    def test_no_data(self, fresh_db):
        result = get_screen_time("2026-04-14", timezone="Australia/Sydney")
        assert result["apps"] == []
        assert result["web_domains"] == []


class TestGetSafariHistory:
    def test_returns_visits(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO safari_history (date, device, visited_at, domain, title, url) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "mac", "2026-04-14T03:00:00Z", "github.com", "GitHub", "https://github.com"),
                ("2026-04-14", "mac", "2026-04-14T04:00:00Z", "google.com", "Google", "https://google.com"),
            ],
        )
        fresh_db.commit()

        result = get_safari_history("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 2
        assert result[0]["domain"] == "github.com"

    def test_domain_filter(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO safari_history (date, device, visited_at, domain, title, url) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "mac", "2026-04-14T03:00:00Z", "github.com", "GH", "https://github.com"),
                ("2026-04-14", "mac", "2026-04-14T04:00:00Z", "youtube.com", "YT", "https://youtube.com"),
            ],
        )
        fresh_db.commit()

        result = get_safari_history("2026-04-14", domain_filter="youtube", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["domain"] == "youtube.com"

    def test_device_filter(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO safari_history (date, device, visited_at, domain, title, url) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "mac", "2026-04-14T03:00:00Z", "github.com", "GH", "https://github.com"),
                ("2026-04-14", "iphone", "2026-04-14T04:00:00Z", "reddit.com", "Reddit", "https://reddit.com"),
            ],
        )
        fresh_db.commit()

        result = get_safari_history("2026-04-14", device="iphone", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["domain"] == "reddit.com"


class TestGetYouTubeHistory:
    def test_returns_youtube(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO youtube_history (date, visited_at, title, url) VALUES (?, ?, ?, ?)",
            ("2026-04-14", "2026-04-14T10:00:00Z", "Cool Video", "https://youtube.com/watch?v=abc"),
        )
        fresh_db.commit()

        result = get_youtube_history("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["title"] == "Cool Video"

    def test_falls_back_to_safari(self, fresh_db):
        """When youtube_history is empty, fall back to Safari filtered by youtube.com."""
        fresh_db.execute(
            "INSERT INTO safari_history (date, device, visited_at, domain, title, url) VALUES (?, ?, ?, ?, ?, ?)",
            ("2026-04-14", "mac", "2026-04-14T10:00:00Z", "youtube.com", "Fallback Video", "https://youtube.com/watch?v=xyz"),
        )
        fresh_db.commit()

        result = get_youtube_history("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["title"] == "Fallback Video"


class TestGetPodcasts:
    def test_returns_podcasts(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO podcasts (date, episode, podcast, duration_seconds, played_at) VALUES (?, ?, ?, ?, ?)",
            ("2026-04-14", "Episode 42", "My Podcast", 1800, "2026-04-14T07:00:00Z"),
        )
        fresh_db.commit()

        result = get_podcasts("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 1
        assert result[0]["episode"] == "Episode 42"
        assert result[0]["podcast"] == "My Podcast"
        assert result[0]["duration_minutes"] == 30.0

    def test_no_data(self, fresh_db):
        result = get_podcasts("2026-04-14", timezone="Australia/Sydney")
        assert result == []


class TestGetClaudeSessions:
    def test_returns_structured_sessions(self, fresh_db):
        fresh_db.executemany(
            "INSERT INTO claude_sessions (date, project, start_time, end_time, duration_min, turns, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-14", "home/server/stack", "2026-04-14 08:00", "2026-04-14 12:00", 240, 42, "Worked on SQLite migration."),
                ("2026-04-14", "dotfiles", "2026-04-14 13:00", "2026-04-14 14:30", 90, 25, "Fixed script timing."),
            ],
        )
        fresh_db.commit()

        result = get_claude_sessions("2026-04-14", timezone="Australia/Sydney")
        assert len(result) == 2
        assert result[0]["project"] == "home/server/stack"
        assert result[0]["duration_minutes"] == 240
        assert result[0]["turns"] == 42
        assert "SQLite" in result[0]["summary"]
        assert result[1]["project"] == "dotfiles"

    def test_no_data_returns_empty(self, fresh_db):
        result = get_claude_sessions("2026-04-14", timezone="Australia/Sydney")
        assert result == []
