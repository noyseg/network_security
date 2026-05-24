"""Integration tests for the dashboard routes."""

import pytest


def _make_campaign(client, template_type="single"):
    r = client.post("/admin/campaigns", data={
        "title": "Test",
        "sender_name": "Demo Co.",
        "subject": "Action required",
        "body_a": "Click below to confirm.",
        "body_b": "Other body" if template_type == "ab" else "",
        "cta_text": "Confirm",
        "landing_path": "/landing/1",
        "template_type": template_type,
    })
    assert r.status_code == 302
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


def _ping(client, cid, event_type, subject, variant="A", metadata=None):
    body = {
        "event_type": event_type,
        "campaign_id": cid,
        "subject_code": subject,
        "variant": variant,
    }
    if metadata is not None:
        body["metadata"] = metadata
    return client.post("/events/ping", json=body)


class TestDashboardShell:
    def test_html_renders(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/admin/dashboard/{cid}")
        assert r.status_code == 200
        assert b"Dashboard" in r.data
        # Chart.js CDN reference is present
        assert b"chart.js" in r.data.lower() or b"chart.umd.js" in r.data.lower()

    def test_html_404_for_unknown_campaign(self, client):
        r = client.get("/admin/dashboard/99999")
        assert r.status_code == 404


class TestDashboardData:
    def test_zero_data_shape(self, client):
        cid = _make_campaign(client)
        r = client.get(f"/admin/dashboard/{cid}/data")
        assert r.status_code == 200
        body = r.get_json()
        assert set(body.keys()) == {"campaign", "totals", "variants"}
        totals = body["totals"]
        for key in ("opens", "clicks", "visits", "submits",
                    "click_rate", "submit_rate",
                    "avg_response_time_ms", "avg_time_on_page_ms"):
            assert key in totals
            assert totals[key] == 0 or totals[key] == 0.0
        assert "A" in body["variants"]
        assert "B" in body["variants"]

    def test_counts_populate_after_funnel(self, client):
        cid = _make_campaign(client)
        # Trigger one open + one click + one visit via the actual routes
        # so the dedup paths run end-to-end.
        client.get(f"/message/{cid}/view?subject=subject-01")
        client.get(f"/landing/{cid}?subject=subject-01&variant=A")
        client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 2},
        )
        r = client.get(f"/admin/dashboard/{cid}/data")
        totals = r.get_json()["totals"]
        assert totals["opens"] == 1
        assert totals["clicks"] == 1
        assert totals["visits"] == 1
        assert totals["submits"] == 1
        assert totals["click_rate"] == 1.0
        assert totals["submit_rate"] == 1.0

    def test_data_404_for_unknown_campaign(self, client):
        r = client.get("/admin/dashboard/99999/data")
        assert r.status_code == 404
