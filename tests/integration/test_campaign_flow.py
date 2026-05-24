"""Integration tests for the campaign authoring routes."""

import pytest


VALID_PAYLOAD = {
    "title": "Demo phish 01",
    "sender_name": "Demo Co.",
    "subject": "Action required",
    "body_a": "Please confirm your account by clicking below.",
    "body_b": "",
    "cta_text": "Confirm now",
    "landing_path": "/landing/1",
    "template_type": "single",
}


class TestCreateCampaign:
    def test_get_form_renders(self, client):
        r = client.get("/admin/campaigns/new")
        assert r.status_code == 200
        assert b"New campaign" in r.data

    def test_valid_post_redirects_to_detail(self, client):
        r = client.post("/admin/campaigns", data=VALID_PAYLOAD)
        assert r.status_code == 302
        assert "/admin/campaigns/" in r.headers["Location"]

    def test_real_brand_sender_is_rejected(self, client):
        bad = dict(VALID_PAYLOAD, sender_name="Bank of America")
        r = client.post("/admin/campaigns", data=bad)
        assert r.status_code == 400
        assert b"real brand" in r.data or b"sender_name" in r.data

    def test_external_landing_path_is_rejected(self, client):
        bad = dict(VALID_PAYLOAD, landing_path="https://evil.example.com/login")
        r = client.post("/admin/campaigns", data=bad)
        assert r.status_code == 400
        assert b"landing_path" in r.data

    def test_ab_requires_body_b(self, client):
        bad = dict(VALID_PAYLOAD, template_type="ab", body_b="")
        r = client.post("/admin/campaigns", data=bad)
        assert r.status_code == 400


class TestListAndDetail:
    def test_list_renders(self, client):
        client.post("/admin/campaigns", data=VALID_PAYLOAD)
        r = client.get("/admin/campaigns")
        assert r.status_code == 200
        assert b"Demo phish 01" in r.data

    def test_detail_renders(self, client):
        r1 = client.post("/admin/campaigns", data=VALID_PAYLOAD)
        loc = r1.headers["Location"]
        r2 = client.get(loc)
        assert r2.status_code == 200
        assert b"Demo Co." in r2.data

    def test_detail_unknown_id_is_404(self, client):
        r = client.get("/admin/campaigns/99999")
        assert r.status_code == 404
