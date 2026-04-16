"""Shared test fixtures for data-mcp tests."""

import os
import tempfile

import pytest

# Set up temp SQLite DB before any source imports
_TMP_DB = os.path.join(tempfile.gettempdir(), "data-mcp-test.db")
os.environ["SQLITE_DB_PATH"] = _TMP_DB


@pytest.fixture
def fresh_db():
    """Provide a clean SQLite database for health/vault query tests."""
    import sqlite3
    import sources.db as db_mod

    # Close any cached connection
    if db_mod._db is not None:
        db_mod._db.close()
        db_mod._db = None

    for path in (_TMP_DB, _TMP_DB + "-wal", _TMP_DB + "-shm"):
        if os.path.exists(path):
            os.unlink(path)
    db_mod.init_db()

    # Return a writable connection for test setup (seeding data)
    db = sqlite3.connect(_TMP_DB, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    yield db
    db.close()

    # Reset cached connection so next test gets a fresh one
    if db_mod._db is not None:
        db_mod._db.close()
        db_mod._db = None
