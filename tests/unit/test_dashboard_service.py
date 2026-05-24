"""Unit tests for ``app.dashboard.service``.

These tests seed events directly through the Logging service (and through
``models`` for raw timestamps) so we can assert that the aggregations
produce the expected numbers on hand-crafted data.
"""

from datetime import datetime, timedelta

import pytest

from app.constants import (
    EVENT_FAKE_SUBMIT_ATTEMPTED,
    EVENT_LANDING_EXITED,
    EVENT_LANDING_VISITED,
    EVENT_LINK_CLICKED,
    EVENT_MESSAGE_OPENED,
)


def _seed_campaign(app, template_type="single", landing_path="/landing/1"):
    """Insert a minimal valid campaign and return its ID."""
    from app.campaign import service as campaign_service
    with app.app_context():
        return campaign_service.create_campaign({
            "title": "Test campaign",
            "sender_name": "Demo Co.",
            "subject": "Action required",
            "body_a": "Click below to confirm.",
            "body_b": "Click below now." if template_type == "ab" else "",
            "cta_text": "Confirm",
            "landing_path": landing_path,
            "template_type": template_type,
        })


def _record(app, *args, **kwargs):
    """Convenience wrapper around the Logging service."""
    from app.logging_mod import service as logging_service
    with app.app_context():
        return logging_service.record_event(*args, **kwargs)


def _set_event_time(app, event_id: int, when: datetime) -> None:
    """Force an event's ``created_at`` to a specific time (test only)."""
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        conn.execute(
            "UPDATE events SET created_at = ? WHERE id = ?",
            (when.strftime("%Y-%m-%d %H:%M:%S"), event_id),
        )
        conn.commit()


# ---------------------------------------------------------------------
# aggregate_campaign
# ---------------------------------------------------------------------


class TestAggregateCampaign:
    def test_zero_events_returns_zeros(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app)
        with app.app_context():
            agg = dashboard_service.aggregate_campaign(cid)
        assert agg["opens"] == 0
        assert agg["clicks"] == 0
        assert agg["visits"] == 0
        assert agg["submits"] == 0
        assert agg["click_rate"] == 0.0
        assert agg["submit_rate"] == 0.0
        assert agg["avg_response_time_ms"] == 0
        assert agg["avg_time_on_page_ms"] == 0

    def test_distinct_subjects_are_counted_once(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app)
        # Same subject opens twice — dedup-once means only one row.
        _record(app, EVENT_MESSAGE_OPENED, cid, "subject-01", "A")
        _record(app, EVENT_MESSAGE_OPENED, cid, "subject-01", "A")
        _record(app, EVENT_MESSAGE_OPENED, cid, "subject-02", "A")
        with app.app_context():
            agg = dashboard_service.aggregate_campaign(cid)
        assert agg["opens"] == 2

    def test_full_funnel_rates(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app)
        # 4 opens, 3 clicks, 3 visits, 2 submits.
        for i in range(1, 5):
            _record(app, EVENT_MESSAGE_OPENED, cid, f"subject-0{i}", "A")
        for i in range(1, 4):
            _record(app, EVENT_LINK_CLICKED, cid, f"subject-0{i}", "A")
            _record(app, EVENT_LANDING_VISITED, cid, f"subject-0{i}", "A")
        for i in range(1, 3):
            _record(
                app, EVENT_FAKE_SUBMIT_ATTEMPTED, cid, f"subject-0{i}", "A",
                metadata={"field_count": 2},
            )
        with app.app_context():
            agg = dashboard_service.aggregate_campaign(cid)
        assert agg["opens"] == 4
        assert agg["clicks"] == 3
        assert agg["visits"] == 3
        assert agg["submits"] == 2
        assert agg["click_rate"] == 0.75
        assert agg["submit_rate"] == 0.5

    def test_unknown_campaign_raises(self, app):
        from app.dashboard import service as dashboard_service
        with app.app_context():
            with pytest.raises(ValueError):
                dashboard_service.aggregate_campaign(99999)


# ---------------------------------------------------------------------
# compare_variants
# ---------------------------------------------------------------------


class TestCompareVariants:
    def test_both_variants_present_even_for_single(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app, template_type="single")
        _record(app, EVENT_MESSAGE_OPENED, cid, "subject-01", "A")
        with app.app_context():
            cmp = dashboard_service.compare_variants(cid)
        assert "A" in cmp and "B" in cmp
        assert cmp["A"]["opens"] == 1
        assert cmp["B"]["opens"] == 0

    def test_ab_split(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app, template_type="ab")
        _record(app, EVENT_MESSAGE_OPENED, cid, "subject-01", "A")
        _record(app, EVENT_MESSAGE_OPENED, cid, "subject-02", "B")
        _record(app, EVENT_LINK_CLICKED, cid, "subject-02", "B")
        with app.app_context():
            cmp = dashboard_service.compare_variants(cid)
        assert cmp["A"]["opens"] == 1
        assert cmp["A"]["clicks"] == 0
        assert cmp["B"]["opens"] == 1
        assert cmp["B"]["clicks"] == 1
        assert cmp["B"]["click_rate"] == 1.0


# ---------------------------------------------------------------------
# Time-based aggregations
# ---------------------------------------------------------------------


class TestTimeAggregations:
    def test_avg_response_time(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app)
        # Subject-01: opens at T+0s, clicks at T+10s -> 10000 ms
        # Subject-02: opens at T+0s, clicks at T+30s -> 30000 ms
        # Mean: 20000 ms
        t0 = datetime(2026, 5, 1, 10, 0, 0)
        e1 = _record(app, EVENT_MESSAGE_OPENED, cid, "subject-01", "A")
        e2 = _record(app, EVENT_LINK_CLICKED, cid, "subject-01", "A")
        e3 = _record(app, EVENT_MESSAGE_OPENED, cid, "subject-02", "A")
        e4 = _record(app, EVENT_LINK_CLICKED, cid, "subject-02", "A")
        _set_event_time(app, e1, t0)
        _set_event_time(app, e2, t0 + timedelta(seconds=10))
        _set_event_time(app, e3, t0)
        _set_event_time(app, e4, t0 + timedelta(seconds=30))
        with app.app_context():
            agg = dashboard_service.aggregate_campaign(cid)
        assert agg["avg_response_time_ms"] == 20000

    def test_avg_time_on_page_falls_back_to_submit(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app)
        # Subject visits at T+0s; no explicit exit, but submits at T+5s.
        t0 = datetime(2026, 5, 1, 10, 0, 0)
        v = _record(app, EVENT_LANDING_VISITED, cid, "subject-01", "A")
        s = _record(
            app, EVENT_FAKE_SUBMIT_ATTEMPTED, cid, "subject-01", "A",
            metadata={"field_count": 2},
        )
        _set_event_time(app, v, t0)
        _set_event_time(app, s, t0 + timedelta(seconds=5))
        with app.app_context():
            agg = dashboard_service.aggregate_campaign(cid)
        assert agg["avg_time_on_page_ms"] == 5000

    def test_landing_exited_is_preferred_over_submit(self, app):
        from app.dashboard import service as dashboard_service
        cid = _seed_campaign(app)
        t0 = datetime(2026, 5, 1, 10, 0, 0)
        v = _record(app, EVENT_LANDING_VISITED, cid, "subject-01", "A")
        s = _record(
            app, EVENT_FAKE_SUBMIT_ATTEMPTED, cid, "subject-01", "A",
            metadata={"field_count": 2},
        )
        x = _record(
            app, EVENT_LANDING_EXITED, cid, "subject-01", "A",
            metadata={"time_on_page_ms": 8000},
        )
        _set_event_time(app, v, t0)
        _set_event_time(app, s, t0 + timedelta(seconds=5))
        _set_event_time(app, x, t0 + timedelta(seconds=12))
        with app.app_context():
            agg = dashboard_service.aggregate_campaign(cid)
        # 12s, not 5s.
        assert agg["avg_time_on_page_ms"] == 12000
