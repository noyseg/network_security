"""Last-line ethics test: scan the SQLite file for credential leaks.

This test runs an end-to-end flow (view -> click -> submit -> exit),
then opens the SQLite file directly and scans every
``events.metadata_json`` row for any string value that looks like it
could be a real credential — defined as any quoted string value of 6+
characters that also contains at least one digit.

If a future code change ever accidentally forwards form data into an
event payload, this test fails loudly even though all other paths
appear fine.
"""

import re


CREDENTIAL_PATTERN = re.compile(r':\s*"([^"]{6,})"')


def _make_campaign(client):
    r = client.post("/admin/campaigns", data={
        "title": "Credentials test",
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


def _all_metadata_json(app, cid):
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        rows = conn.execute(
            "SELECT id, event_type, metadata_json FROM events "
            "WHERE campaign_id = ?",
            (cid,),
        ).fetchall()
    return [(r["id"], r["event_type"], r["metadata_json"]) for r in rows]


def _scan_for_credentials(metadata_json: str):
    """Return any captured strings of 6+ chars containing at least one digit."""
    if not metadata_json:
        return []
    return [
        match
        for match in CREDENTIAL_PATTERN.findall(metadata_json)
        if any(c.isdigit() for c in match)
    ]


class TestNoCredentialsStored:
    def test_full_flow_does_not_leak_anything_looking_like_a_password(
        self, app, client
    ):
        cid = _make_campaign(client)

        # End-to-end flow that exercises every event-producing route.
        client.get(f"/message/{cid}/view?subject=subject-01")
        client.get(f"/landing/{cid}?subject=subject-01&variant=A")
        client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
        })
        client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 2},
        )
        client.post("/events/ping", json={
            "event_type": "landing_exited",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
            "metadata": {"time_on_page_ms": 12345},
        })

        rows = _all_metadata_json(app, cid)
        assert rows, "expected events to have been written"

        leaks = []
        for event_id, event_type, raw in rows:
            for hit in _scan_for_credentials(raw):
                leaks.append((event_id, event_type, hit))

        assert not leaks, (
            "events.metadata_json contains string value(s) that look like "
            f"real credentials: {leaks}"
        )

    def test_attempt_to_inject_password_key_is_rejected(self, app, client):
        """Even if a future client tries to attach a sensitive key via the
        ping endpoint, the Logging service must reject it."""
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
            "metadata": {"password": "hunter2"},
        })
        assert r.status_code == 400

        # And the row should not exist in the DB.
        from app import db as db_module
        with app.app_context():
            conn = db_module.get_connection()
            cnt = conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE campaign_id = ?",
                (cid,),
            ).fetchone()
        assert int(cnt["n"]) == 0
