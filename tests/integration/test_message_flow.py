"""Integration tests for the message routes (preview + view + pixel)."""

from app.constants import EVENT_MESSAGE_OPENED


def _make_campaign(client, **overrides):
    payload = {
        "title": "Test",
        "sender_name": "Demo Co.",
        "subject": "Action required",
        "body_a": "Click below to confirm.",
        "body_b": "",
        "cta_text": "Confirm",
        "landing_path": "/landing/1",
        "template_type": "single",
    }
    payload.update(overrides)
    r = client.post("/admin/campaigns", data=payload)
    assert r.status_code == 302
    # Location is "/admin/campaigns/<id>"
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


def _count_events(app, campaign_id, event_type):
    from app import models
    with app.app_context():
        return models.count_distinct_subjects_by_event(campaign_id, event_type)


class TestPreview:
    def test_preview_renders_template(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/message/{cid}/preview")
        assert r.status_code == 200
        assert b"SIMULATED MESSAGE" in r.data

    def test_preview_does_not_log(self, app, client):
        cid = _make_campaign(client)
        client.get(f"/message/{cid}/preview")
        assert _count_events(app, cid, EVENT_MESSAGE_OPENED) == 0

    def test_preview_cta_points_at_landing_preview(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/message/{cid}/preview")
        # In preview the lure must lead to the side-effect-free landing
        # preview, not the real (subject-required, logging) landing route.
        assert f"/landing/{cid}/preview".encode() in r.data


class TestSubjectView:
    def test_view_renders(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/message/{cid}/view?subject=subject-01")
        assert r.status_code == 200
        assert b"SIMULATED MESSAGE" in r.data

    def test_view_logs_message_opened(self, app, client):
        cid = _make_campaign(client)
        client.get(f"/message/{cid}/view?subject=subject-01")
        assert _count_events(app, cid, EVENT_MESSAGE_OPENED) == 1

    def test_view_is_deduplicated_per_subject(self, app, client):
        cid = _make_campaign(client)
        client.get(f"/message/{cid}/view?subject=subject-01")
        client.get(f"/message/{cid}/view?subject=subject-01")
        client.get(f"/message/{cid}/view?subject=subject-01")
        assert _count_events(app, cid, EVENT_MESSAGE_OPENED) == 1

    def test_view_requires_subject_param(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/message/{cid}/view")
        assert r.status_code == 400


class TestPixel:
    def test_pixel_returns_png(self, client):
        cid = _make_campaign(client)
        r = client.get(
            f"/message/{cid}/pixel?subject=subject-01&variant=A"
        )
        assert r.status_code == 200
        assert r.mimetype == "image/png"
        assert r.data.startswith(b"\x89PNG")

    def test_pixel_logs_message_opened(self, app, client):
        cid = _make_campaign(client)
        client.get(f"/message/{cid}/pixel?subject=subject-01&variant=A")
        assert _count_events(app, cid, EVENT_MESSAGE_OPENED) == 1

    def test_pixel_without_subject_renders_but_does_not_log(self, app, client):
        cid = _make_campaign(client)
        r = client.get(f"/message/{cid}/pixel")
        assert r.status_code == 200
        assert _count_events(app, cid, EVENT_MESSAGE_OPENED) == 0
