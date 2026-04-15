"""Shared test fixtures for data-ingest tests."""

import os
import tempfile

import pytest

# Create a single temp DB path used by all test modules.
# Must be set before any import of db module.
_TMP_DB = os.path.join(tempfile.gettempdir(), "data-ingest-test.db")
os.environ["SQLITE_DB_PATH"] = _TMP_DB
os.environ.setdefault("INGEST_WRITE_TOKEN", "test-token-123")

from db import init_db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-initialize database before each test."""
    for path in (_TMP_DB, _TMP_DB + "-wal", _TMP_DB + "-shm"):
        if os.path.exists(path):
            os.unlink(path)
    init_db()
    yield
