"""Tests for ingest server endpoints."""

import pytest
from starlette.testclient import TestClient

from server import app


@pytest.fixture
def client():
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-token-123"}


class TestHealthCheck:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestIngestHealth:
    def test_no_auth_returns_401(self, client):
        r = client.post("/ingest/health", json={"data": {}})
        assert r.status_code == 401

    def test_bad_token_returns_401(self, client):
        r = client.post(
            "/ingest/health",
            json={"data": {}},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401

    def test_invalid_json_returns_400(self, client):
        r = client.post(
            "/ingest/health",
            content=b"not json",
            headers={**AUTH, "Content-Type": "application/json"},
        )
        assert r.status_code == 400

    def test_valid_payload_returns_ok(self, client):
        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "step_count",
                        "units": "count",
                        "data": [{"date": "2026-04-14 06:00:00 +1000", "qty": 8423}],
                    }
                ],
                "workouts": [],
            }
        }
        r = client.post("/ingest/health", json=payload, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_empty_payload_returns_ok(self, client):
        r = client.post("/ingest/health", json={"data": {}}, headers=AUTH)
        assert r.status_code == 200


class TestIngestVault:
    def test_no_auth_returns_401(self, client):
        r = client.post("/ingest/vault", json={"date": "2026-04-14", "files": {}})
        assert r.status_code == 401

    def test_missing_date_returns_400(self, client):
        r = client.post("/ingest/vault", json={"files": {}}, headers=AUTH)
        assert r.status_code == 400

    def test_valid_payload_returns_ok(self, client):
        payload = {
            "date": "2026-04-14",
            "files": {
                "screentime.csv": "identifier,type,seconds\ncom.apple.Safari,app,3600",
                "claude-sessions.md": "## Session 1\nDid some work.",
            },
        }
        r = client.post("/ingest/vault", json=payload, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
