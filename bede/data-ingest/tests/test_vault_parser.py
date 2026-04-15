"""Tests for vault_parser — CSV-in-JSON payload parsing."""

import pytest

from db import get_db
from vault_parser import parse_vault_payload


class TestScreenTime:
    def test_mac_screentime(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "screentime.csv": "identifier,type,seconds\ncom.apple.Safari,app,3600\ncom.google.Chrome,app,1800",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 2

        db = get_db()
        results = db.execute("SELECT * FROM screen_time WHERE date = '2026-04-14' ORDER BY seconds DESC").fetchall()
        assert len(results) == 2
        assert results[0]["identifier"] == "com.apple.Safari"
        assert results[0]["seconds"] == 3600
        assert results[0]["device"] == "mac"
        assert results[0]["entry_type"] == "app"

    def test_iphone_screentime(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "iphone-screentime.csv": "identifier,type,seconds\ncom.apple.mobilesafari,app,1200",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM screen_time").fetchone()
        assert row["device"] == "iphone"

    def test_web_domain_entries(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "screentime.csv": "identifier,type,seconds,domain\ngithub.com,web,900,github.com",
            },
        }
        parse_vault_payload(payload)

        db = get_db()
        row = db.execute("SELECT * FROM screen_time").fetchone()
        assert row["entry_type"] == "web"
        assert row["identifier"] == "github.com"

    def test_alternative_column_names(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "screentime.csv": "app,duration\nSafari,3600",
            },
        }
        parse_vault_payload(payload)

        db = get_db()
        row = db.execute("SELECT * FROM screen_time").fetchone()
        assert row["identifier"] == "Safari"
        assert row["seconds"] == 3600

    def test_daily_replacement(self):
        """Second ingest for same date+device replaces all rows."""
        payload1 = {
            "date": "2026-04-14",
            "files": {"screentime.csv": "identifier,type,seconds\nSafari,app,3600\nChrome,app,1800"},
        }
        payload2 = {
            "date": "2026-04-14",
            "files": {"screentime.csv": "identifier,type,seconds\nFirefox,app,2400"},
        }
        parse_vault_payload(payload1)
        parse_vault_payload(payload2)

        db = get_db()
        results = db.execute("SELECT * FROM screen_time WHERE device = 'mac'").fetchall()
        assert len(results) == 1
        assert results[0]["identifier"] == "Firefox"


class TestSafariHistory:
    def test_mac_safari(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "safari-pages.csv": "visited_at,domain,title,url\n2026-04-14T03:15:00Z,github.com,GitHub,https://github.com\n2026-04-14T04:00:00Z,google.com,Google,https://google.com",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 2

        db = get_db()
        results = db.execute("SELECT * FROM safari_history ORDER BY visited_at").fetchall()
        assert results[0]["domain"] == "github.com"
        assert results[0]["device"] == "mac"

    def test_iphone_safari(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "iphone-safari-pages.csv": "visited_at,domain,title,url\n2026-04-14T05:00:00Z,reddit.com,Reddit,https://reddit.com",
            },
        }
        parse_vault_payload(payload)

        db = get_db()
        row = db.execute("SELECT * FROM safari_history").fetchone()
        assert row["device"] == "iphone"

    def test_skips_rows_without_visited_at(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "safari-pages.csv": "visited_at,domain,title,url\n,github.com,GitHub,https://github.com",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 0


class TestYouTubeHistory:
    def test_youtube(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "youtube.csv": "visited_at,title,url\n2026-04-14T10:00:00Z,Cool Video,https://youtube.com/watch?v=abc123",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM youtube_history").fetchone()
        assert row["title"] == "Cool Video"
        assert "abc123" in row["url"]


class TestPodcasts:
    def test_podcasts(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "podcasts.csv": "episode,podcast,duration_seconds,played_at\nEp 42,My Podcast,1800,2026-04-14T07:00:00Z",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM podcasts").fetchone()
        assert row["episode"] == "Ep 42"
        assert row["podcast"] == "My Podcast"
        assert row["duration_seconds"] == 1800

    def test_alternative_column_names(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "podcasts.csv": "title,show,duration,played_at\nEp 1,Tech Talk,2400,2026-04-14T08:00:00Z",
            },
        }
        parse_vault_payload(payload)

        db = get_db()
        row = db.execute("SELECT * FROM podcasts").fetchone()
        assert row["episode"] == "Ep 1"
        assert row["podcast"] == "Tech Talk"
        assert row["duration_seconds"] == 2400

    def test_skips_rows_without_played_at(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "podcasts.csv": "episode,podcast,duration_seconds,played_at\nEp 1,Show,,",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 0


class TestClaudeSessions:
    def test_inserts_markdown(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "claude-sessions.md": "## Session 1\nWorked on SQLite migration.\n## Session 2\nMore work.",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 1

        db = get_db()
        row = db.execute("SELECT * FROM claude_sessions").fetchone()
        assert row["date"] == "2026-04-14"
        assert "Session 2" in row["content"]

    def test_replaces_on_re_ingest(self):
        payload1 = {"date": "2026-04-14", "files": {"claude-sessions.md": "v1"}}
        payload2 = {"date": "2026-04-14", "files": {"claude-sessions.md": "v2"}}
        parse_vault_payload(payload1)
        parse_vault_payload(payload2)

        db = get_db()
        row = db.execute("SELECT * FROM claude_sessions").fetchone()
        assert row["content"] == "v2"
        assert db.execute("SELECT COUNT(*) FROM claude_sessions").fetchone()[0] == 1

    def test_empty_content_skipped(self):
        payload = {"date": "2026-04-14", "files": {"claude-sessions.md": "  "}}
        rows = parse_vault_payload(payload)
        assert rows == 0


class TestMixedPayload:
    def test_multiple_files_in_one_payload(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "screentime.csv": "identifier,type,seconds\nSafari,app,3600",
                "safari-pages.csv": "visited_at,domain,title,url\n2026-04-14T03:00:00Z,github.com,GH,https://github.com",
                "youtube.csv": "visited_at,title,url\n2026-04-14T10:00:00Z,Video,https://youtube.com/v",
                "podcasts.csv": "episode,podcast,duration_seconds,played_at\nEp1,Show,1200,2026-04-14T07:00:00Z",
                "claude-sessions.md": "## Session",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 5  # 1 + 1 + 1 + 1 + 1

    def test_unknown_files_ignored(self):
        payload = {
            "date": "2026-04-14",
            "files": {
                "screentime.csv": "identifier,type,seconds\nSafari,app,3600",
                "random.txt": "some content",
            },
        }
        rows = parse_vault_payload(payload)
        assert rows == 1  # only screentime

    def test_empty_date_returns_zero(self):
        payload = {"date": "", "files": {"screentime.csv": "identifier,type,seconds\nSafari,app,3600"}}
        rows = parse_vault_payload(payload)
        assert rows == 0
