"""Integration tests for the landing flow.

These tests are the strictest in the suite: they assert that no field
value and no field name ever lands in ``events.metadata_json``.
"""

import json

import pytest

from app.constants import (
    EVENT_FAKE_SUBMIT_ATTEMPTED,
    EVENT_LANDING_VISITED,
    EVENT_LINK_CLICKED,
)


def _make_campaign(client):
    r = client.post("/admin/campaigns", data={
        "title": "Test",
        "sender_name": "Demo Co.",
        "subject": "Action required",
        "body_a": "Click below to confirm.",
        "body_b": "",
        "cta_text": "Confirm",
        "landing_path": "/landing/1",
        "template_type": "single",
    })
    assert r.status_code == 302
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


def _count(app, cid, event_type):
    from app import models
    with app.app_context():
        return models.count_distinct_subjects_by_event(cid, event_type)


def _all_metadata(app, cid):
    """Return the raw metadata_json strings for every event row."""
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        rows = conn.execute(
            "SELECT metadata_json FROM events WHERE campaign_id = ?",
            (cid,),
        ).fetchall()
    return [r["metadata_json"] for r in rows]


class TestClickAndVisit:
    def test_landing_get_logs_click_and_visit(self, app, client):
        cid = _make_campaign(client)
        r = client.get(f"/landing/{cid}?subject=subject-01&variant=A")
        assert r.status_code == 200
        assert _count(app, cid, EVENT_LINK_CLICKED) == 1
        assert _count(app, cid, EVENT_LANDING_VISITED) == 1

    def test_landing_is_idempotent_per_subject(self, app, client):
        cid = _make_campaign(client)
        for _ in range(3):
            client.get(f"/landing/{cid}?subject=subject-01&variant=A")
        assert _count(app, cid, EVENT_LINK_CLICKED) == 1
        assert _count(app, cid, EVENT_LANDING_VISITED) == 1


class TestFakeSubmit:
    def test_submit_inserts_event(self, app, client):
        cid = _make_campaign(client)
        r = client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 2},
        )
        assert r.status_code == 200
        body = r.get_json()
        # Redirect points at the debrief page; a query string on the URL
        # is fine (it lets the debrief know who arrived).
        redirect_url = body.get("redirect", "")
        assert redirect_url.startswith("/landing/debrief")
        assert _count(app, cid, EVENT_FAKE_SUBMIT_ATTEMPTED) == 1

    def test_metadata_contains_only_field_count(self, app, client):
        cid = _make_campaign(client)
        client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 2},
        )
        rows = _all_metadata(app, cid)
        submit_metas = [json.loads(r) for r in rows if r]
        assert {"field_count": 2} in submit_metas
        for meta in submit_metas:
            if "field_count" in meta:
                assert set(meta.keys()) == {"field_count"}

    def test_negative_field_count_is_rejected(self, app, client):
        cid = _make_campaign(client)
        r = client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": -1},
        )
        assert r.status_code == 400

    def test_excessive_field_count_is_rejected(self, app, client):
        cid = _make_campaign(client)
        r = client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 999},
        )
        assert r.status_code == 400


class TestDebrief:
    def test_debrief_renders(self, client):
        r = client.get("/landing/debrief")
        assert r.status_code == 200


class TestNoSensitiveValuesEverStored:
    """No row in events.metadata_json should contain a string value of
    any meaningful length. The only string-shaped values we accept are
    short variant codes and the integer field_count.
    """

    def test_full_flow_no_string_values_in_metadata(self, app, client):
        cid = _make_campaign(client)
        client.get(f"/landing/{cid}?subject=subject-01&variant=A")
        client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 3},
        )
        rows = _all_metadata(app, cid)
        for raw in rows:
            if not raw:
                continue
            meta = json.loads(raw)
            for k, v in meta.items():
                if isinstance(v, str):
                    pytest.fail(
                        f"events.metadata_json contains a string value "
                        f"under key {k!r}: {v!r}"
                    )


class TestLandingPreview:
    """The admin landing preview must be completely side-effect free."""

    def test_preview_renders_the_login_form(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/landing/{cid}/preview")
        assert r.status_code == 200
        assert b"fake-login-form" in r.data
        assert b"PREVIEW" in r.data

    def test_preview_records_no_events(self, app, client):
        cid = _make_campaign(client)
        client.get(f"/landing/{cid}/preview")
        client.get(f"/landing/{cid}/preview?variant=B")
        from app import db as db_module
        with app.app_context():
            conn = db_module.get_connection()
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE campaign_id = ?",
                (cid,),
            ).fetchone()["n"]
        assert n == 0

    def test_preview_does_not_load_tracker_js(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/landing/{cid}/preview")
        assert b"tracker.js" not in r.data

    def test_preview_unknown_campaign_404(self, client):
        r = client.get("/landing/9999/preview")
        assert r.status_code == 404
