"""DEMO_MODE seed behavior.

Builds an app with DEMO_MODE on against a fresh temp DB and asserts the
seeder populates two campaigns plus a sample funnel, is idempotent, and
produces only ethics-clean campaign rows.
"""

import os
import tempfile

import pytest


@pytest.fixture
def demo_app(monkeypatch):
    from config import Config

    fd, path = tempfile.mkstemp(prefix="phishing_demo_test_", suffix=".sqlite")
    os.close(fd)
    os.remove(path)  # start with no file so schema + seed run on a clean DB

    monkeypatch.setattr(Config, "DB_PATH", path)
    monkeypatch.setattr(Config, "DEMO_MODE", True)

    from app import create_app
    app = create_app()
    yield app

    try:
        os.remove(path)
    except OSError:
        pass


def _campaigns(app):
    from app import models
    with app.app_context():
        return models.list_campaigns()


def _event_rows(app):
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        return [dict(r) for r in conn.execute(
            "SELECT campaign_id, variant, event_type FROM events"
        ).fetchall()]


class TestDemoSeed:
    def test_seeds_two_campaigns(self, demo_app):
        camps = _campaigns(demo_app)
        assert len(camps) == 2
        assert sorted(c["template_type"] for c in camps) == ["ab", "single"]

    def test_seeds_a_funnel(self, demo_app):
        ets = {r["event_type"] for r in _event_rows(demo_app)}
        assert "message_opened" in ets
        assert "fake_submit_attempted" in ets

    def test_ab_campaign_has_both_variants(self, demo_app):
        ab = next(c for c in _campaigns(demo_app) if c["template_type"] == "ab")
        variants = {
            r["variant"]
            for r in _event_rows(demo_app)
            if r["campaign_id"] == ab["id"]
        }
        assert variants == {"A", "B"}

    def test_seed_is_idempotent(self, demo_app):
        # Rebuilding the app against the already-seeded DB must not add rows.
        from app import create_app
        create_app()
        assert len(_campaigns(demo_app)) == 2

    def test_seeded_campaigns_are_ethics_clean(self, demo_app):
        from app.validators import is_landing_link_local, is_sender_fictional
        for c in _campaigns(demo_app):
            assert is_sender_fictional(c["sender_name"]), c["sender_name"]
            assert is_landing_link_local(c["landing_path"]), c["landing_path"]
