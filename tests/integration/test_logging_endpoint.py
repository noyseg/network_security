"""Integration tests for ``POST /events/ping``."""


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


class TestPingValid:
    def test_form_interaction_started_is_accepted(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
        })
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert isinstance(body["event_id"], int)

    def test_landing_exited_with_time_metadata(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "landing_exited",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
            "metadata": {"time_on_page_ms": 12345},
        })
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


class TestPingRejections:
    def test_unknown_event_type_is_rejected(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "password_submitted",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
        })
        assert r.status_code == 400
        assert b"allow-list" in r.data

    def test_unknown_campaign_is_rejected(self, client):
        r = client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": 99999,
            "subject_code": "subject-01",
            "variant": "A",
        })
        assert r.status_code == 400

    def test_sensitive_metadata_is_rejected(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
            "metadata": {"password": "hunter2"},
        })
        assert r.status_code == 400
        assert b"sensitive key" in r.data

    def test_bad_variant_is_rejected(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "Z",
        })
        assert r.status_code == 400

    def test_non_json_body_is_rejected(self, client):
        r = client.post(
            "/events/ping",
            data="not json",
            content_type="text/plain",
        )
        assert r.status_code == 400

    def test_bad_subject_code_is_rejected(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "1starts-with-digit",
            "variant": "A",
        })
        assert r.status_code == 400
