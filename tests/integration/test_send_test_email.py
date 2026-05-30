"""Integration tests for the admin 'Send test email' action.

These tests pin the safe-by-default behavior: in sandbox mode (the default),
emails go to a local outbox and never touch the network, real recipient
addresses never enter the ``events`` table, and SMTP is not invoked.
"""


def _make_campaign(client):
    r = client.post("/admin/campaigns", data={
        "title": "Send-test campaign",
        "sender_name": "Demo Co.",
        "subject": "Action needed on your demo account",
        "body_a": "Hi,\n\nPlease confirm your demo account using the link.",
        "body_b": "",
        "cta_text": "Confirm now",
        "landing_path": "/landing/1",
        "template_type": "single",
    })
    assert r.status_code == 302
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


def _set_recipients(client, cid, lines):
    r = client.post(
        f"/admin/campaigns/{cid}/recipients",
        data={"recipients": "\n".join(lines)},
    )
    assert r.status_code == 200


def _outbox(app, cid):
    from app import models
    with app.app_context():
        return models.list_outbox(cid)


def _events_rows(app, cid):
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        return [dict(r) for r in conn.execute(
            "SELECT event_type, metadata_json FROM events WHERE campaign_id = ?",
            (cid,),
        ).fetchall()]


class TestSendTest:
    def test_no_recipients_returns_clear_error(self, client):
        cid = _make_campaign(client)
        r = client.post(f"/admin/campaigns/{cid}/send-test")
        assert r.status_code == 400
        body = r.get_json()
        assert body["ok"] is False
        assert "no recipients" in body["error"].lower()

    def test_sandbox_send_writes_outbox_and_summary(self, app, client):
        cid = _make_campaign(client)
        _set_recipients(client, cid, [
            "alice@example.test",
            "bob@example.test",
            "carol@example.test",
        ])
        r = client.post(f"/admin/campaigns/{cid}/send-test")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        summary = body["summary"]
        assert summary == {
            "total": 3,
            "sent": 3,
            "failed": 0,
            "errors": [],
        }

        rows = _outbox(app, cid)
        assert {r["to_addr"] for r in rows} == {
            "alice@example.test",
            "bob@example.test",
            "carol@example.test",
        }
        for r in rows:
            assert r["mode"] == "sandbox"
            assert r["subject"].startswith("[SIMULATION] ")
            # link should be present in the body and use the configured base URL
            assert "/message/" in r["body"]
            assert "?subject=r" in r["body"]  # pseudonymous code, not the email

    def test_no_recipient_email_lands_in_events(self, app, client):
        cid = _make_campaign(client)
        _set_recipients(client, cid, ["victim@example.test"])
        client.post(f"/admin/campaigns/{cid}/send-test")

        # The events table must NEVER contain a real email address.
        rows = _events_rows(app, cid)
        for row in rows:
            assert "victim@example.test" not in (row["metadata_json"] or "")

    def test_sandbox_never_calls_smtp(self, app, client, monkeypatch):
        # If sandbox accidentally invoked SMTP, this would raise.
        import smtplib

        class _Boom:
            def __init__(self, *_a, **_kw):
                raise AssertionError("sandbox must not open an SMTP connection")

        monkeypatch.setattr(smtplib, "SMTP", _Boom)

        cid = _make_campaign(client)
        _set_recipients(client, cid, ["alice@example.test"])
        r = client.post(f"/admin/campaigns/{cid}/send-test")
        assert r.status_code == 200
        assert r.get_json()["summary"]["sent"] == 1
