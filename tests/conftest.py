"""Shared pytest fixtures.

The fixtures point the application at a temporary SQLite file per test
session so production data is never touched.
"""

import os
import sys
import tempfile

import pytest


# Make the project root importable when pytest is invoked from anywhere.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def _temp_db_path():
    """One temp SQLite file for the whole test session."""
    fd, path = tempfile.mkstemp(prefix="phishing_sim_test_", suffix=".sqlite")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture
def app(_temp_db_path, monkeypatch):
    """Build a Flask app pointed at a fresh schema in the temp DB."""
    from config import Config
    monkeypatch.setattr(Config, "DB_PATH", _temp_db_path)

    # Wipe and re-create the schema for each test that uses the app fixture.
    if os.path.exists(_temp_db_path):
        os.remove(_temp_db_path)

    from app import create_app
    app = create_app()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
