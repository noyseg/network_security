"""Dashboard service.

Aggregates event rows into the headline numbers the dashboard UI shows.
Reads only — never writes. Per the architecture rules in
``IMPLEMENTATION_PLAN`` Section 1.2, this is the only module besides
the Logging service that touches the ``events`` table.

Public API:

* ``aggregate_campaign(campaign_id)`` — totals across both variants.
* ``compare_variants(campaign_id)``    — per-variant breakdown.

Both raise ``ValueError`` when the campaign does not exist.
"""

from datetime import datetime
from typing import Optional

from app import models
from app.constants import (
    EVENT_FAKE_SUBMIT_ATTEMPTED,
    EVENT_LANDING_EXITED,
    EVENT_LANDING_VISITED,
    EVENT_LINK_CLICKED,
    EVENT_MESSAGE_OPENED,
    VARIANT_A,
    VARIANT_B,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _parse_dt(value) -> Optional[datetime]:
    """Coerce a SQLite text/datetime value into a datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # SQLite stores ``CURRENT_TIMESTAMP`` as ISO text, e.g. '2026-05-24 10:15:22'.
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _avg_response_time_ms(
    campaign_id: int, variant: Optional[str] = None
) -> int:
    """Mean of per-subject ``(first link_clicked) - (first message_opened)``.

    A subject contributes only if both events exist and the click is
    not earlier than the open (clicks before opens are treated as a
    data anomaly and skipped). Returns 0 when no subject contributes.
    """
    subjects = models.list_subjects_with_event(
        campaign_id, EVENT_MESSAGE_OPENED, variant
    )
    deltas = []
    for sid in subjects:
        opened = _parse_dt(
            models.get_first_event_time(
                campaign_id, sid, EVENT_MESSAGE_OPENED
            )
        )
        clicked = _parse_dt(
            models.get_first_event_time(
                campaign_id, sid, EVENT_LINK_CLICKED
            )
        )
        if opened and clicked and clicked >= opened:
            deltas.append(int((clicked - opened).total_seconds() * 1000))
    if not deltas:
        return 0
    return int(sum(deltas) / len(deltas))


def _avg_time_on_page_ms(
    campaign_id: int, variant: Optional[str] = None
) -> int:
    """Mean of per-subject ``(latest exit) - (first landing_visited)``.

    Uses ``landing_exited`` when present; falls back to
    ``fake_submit_attempted`` as the exit marker when no
    ``landing_exited`` row exists. Returns 0 when no subject has any
    landing visit.
    """
    subjects = models.list_subjects_with_event(
        campaign_id, EVENT_LANDING_VISITED, variant
    )
    deltas = []
    for sid in subjects:
        visited = _parse_dt(
            models.get_first_event_time(
                campaign_id, sid, EVENT_LANDING_VISITED
            )
        )
        exited = _parse_dt(
            models.get_latest_event_time(
                campaign_id, sid, EVENT_LANDING_EXITED
            )
        )
        if exited is None:
            exited = _parse_dt(
                models.get_latest_event_time(
                    campaign_id, sid, EVENT_FAKE_SUBMIT_ATTEMPTED
                )
            )
        if visited and exited and exited >= visited:
            deltas.append(int((exited - visited).total_seconds() * 1000))
    if not deltas:
        return 0
    return int(sum(deltas) / len(deltas))


def _aggregate_block(
    campaign_id: int, variant: Optional[str] = None
) -> dict:
    """Compute the headline numbers, optionally filtered by variant."""
    opens = models.count_distinct_subjects_by_event(
        campaign_id, EVENT_MESSAGE_OPENED, variant
    )
    clicks = models.count_distinct_subjects_by_event(
        campaign_id, EVENT_LINK_CLICKED, variant
    )
    visits = models.count_distinct_subjects_by_event(
        campaign_id, EVENT_LANDING_VISITED, variant
    )
    submits = models.count_distinct_subjects_by_event(
        campaign_id, EVENT_FAKE_SUBMIT_ATTEMPTED, variant
    )
    click_rate = (clicks / opens) if opens else 0.0
    submit_rate = (submits / opens) if opens else 0.0
    return {
        "opens": opens,
        "clicks": clicks,
        "visits": visits,
        "submits": submits,
        "click_rate": round(click_rate, 4),
        "submit_rate": round(submit_rate, 4),
        "avg_response_time_ms": _avg_response_time_ms(campaign_id, variant),
        "avg_time_on_page_ms": _avg_time_on_page_ms(campaign_id, variant),
    }


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def aggregate_campaign(campaign_id: int) -> dict:
    """Headline numbers for one campaign, across both variants.

    Returns a dict with keys: ``opens``, ``clicks``, ``visits``,
    ``submits``, ``click_rate``, ``submit_rate``,
    ``avg_response_time_ms``, ``avg_time_on_page_ms``.

    Raises ``ValueError`` when the campaign does not exist.
    """
    if models.get_campaign_by_id(campaign_id) is None:
        raise ValueError(f"campaign {campaign_id} does not exist")
    return _aggregate_block(campaign_id, variant=None)


def compare_variants(campaign_id: int) -> dict:
    """Per-variant breakdown.

    Returns ``{"A": {...}, "B": {...}}`` with the same keys as
    ``aggregate_campaign``. Always includes both variants; for a
    campaign with ``template_type='single'`` the B values will be 0.

    Raises ``ValueError`` when the campaign does not exist.
    """
    if models.get_campaign_by_id(campaign_id) is None:
        raise ValueError(f"campaign {campaign_id} does not exist")
    return {
        VARIANT_A: _aggregate_block(campaign_id, variant=VARIANT_A),
        VARIANT_B: _aggregate_block(campaign_id, variant=VARIANT_B),
    }
