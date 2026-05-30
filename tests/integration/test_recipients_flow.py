"""Integration tests for the per-campaign recipients UI/API."""


def _make_campaign(client):
    r = client.post("/admin/campaigns", data={
        "title": "Recipients test",
        "sender_name": "Demo Co.",
        "subject": "x",
        "body_a": "x",
        "body_b": "",
        "cta_text": "x",
        "landing_path": "/landing/1",
        "template_type": "single",
    })
    assert r.status_code == 302
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


def _list(app, cid):
    from app import models
    with app.app_context():
        return models.list_recipients(cid)


class TestDetailShowsRecipientsSection:
    def test_detail_renders_recipients_section(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/admin/campaigns/{cid}")
        assert r.status_code == 200
        assert b"Recipients" in r.data
        assert b'name="recipients"' in r.data
        assert b"Send test email" in r.data


class TestUpdateRecipients:
    def test_saves_clean_list(self, app, client):
        cid = _make_campaign(client)
        r = client.post(
            f"/admin/campaigns/{cid}/recipients",
            data={"recipients": "alice@example.test\nbob@example.test"},
        )
        assert r.status_code == 200
        assert b"Saved 2 recipient" in r.data
        assert _list(app, cid) == ["alice@example.test", "bob@example.test"]

    def test_trims_dedupes_and_ignores_blanks(self, app, client):
        cid = _make_campaign(client)
        raw = (
            "  alice@example.test  \n"
            "\n"
            "bob@example.test\n"
            "ALICE@example.test\n"   # case-insensitive duplicate
            "  \n"
            "carol@example.test,dave@example.test"  # commas also split
        )
        r = client.post(
            f"/admin/campaigns/{cid}/recipients",
            data={"recipients": raw},
        )
        assert r.status_code == 200
        assert _list(app, cid) == [
            "alice@example.test",
            "bob@example.test",
            "carol@example.test",
            "dave@example.test",
        ]

    def test_invalid_email_is_rejected_with_clear_error(self, app, client):
        cid = _make_campaign(client)
        r = client.post(
            f"/admin/campaigns/{cid}/recipients",
            data={"recipients": "alice@example.test\nnot-an-email"},
        )
        assert r.status_code == 400
        assert b"invalid email address" in r.data
        # Nothing should be persisted on failure.
        assert _list(app, cid) == []

    def test_empty_textarea_clears_the_list(self, app, client):
        cid = _make_campaign(client)
        client.post(
            f"/admin/campaigns/{cid}/recipients",
            data={"recipients": "alice@example.test"},
        )
        assert _list(app, cid) == ["alice@example.test"]
        r = client.post(
            f"/admin/campaigns/{cid}/recipients",
            data={"recipients": ""},
        )
        assert r.status_code == 200
        assert _list(app, cid) == []

    def test_unknown_campaign_is_404(self, client):
        r = client.post(
            "/admin/campaigns/9999/recipients",
            data={"recipients": "alice@example.test"},
        )
        assert r.status_code == 404
