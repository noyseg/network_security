"""Campaign service.

Owns the lifecycle of campaign objects: validate authoring input against
the project's ethics rules, then delegate persistence to ``app.models``.

Routes call this layer; this layer is the only entry point that turns a
raw authoring payload into a row in ``campaigns``.
"""

from typing import Optional

from app import models
from app.constants import TEMPLATE_AB, TEMPLATE_SINGLE
from app.validators import (
    is_landing_link_local,
    is_sender_fictional,
    is_template_safe,
)
from config import Config


_REQUIRED_FIELDS = (
    "title",
    "sender_name",
    "subject",
    "body_a",
    "cta_text",
    "landing_path",
    "template_type",
)


def create_campaign(payload: dict) -> int:
    """Validate ``payload`` and insert it as a new campaign row.

    Raises ``ValueError`` for any ethics-rule violation or bad shape. The
    error message names the field at fault so the form template can show
    it back to the instructor.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")

    # --- Required fields + whitespace strip ------------------------------
    cleaned: dict = {}
    for field in _REQUIRED_FIELDS:
        value = payload.get(field)
        if value is None:
            raise ValueError(f"missing required field: {field}")
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError(f"field '{field}' must not be empty")
        cleaned[field] = value

    # Optional body_b
    body_b = payload.get("body_b")
    if isinstance(body_b, str):
        body_b = body_b.strip() or None
    cleaned["body_b"] = body_b

    # --- Length limits ----------------------------------------------------
    if len(cleaned["title"]) > Config.MAX_TITLE_LENGTH:
        raise ValueError(
            f"title must be <= {Config.MAX_TITLE_LENGTH} characters"
        )
    if len(cleaned["body_a"]) > Config.MAX_BODY_LENGTH:
        raise ValueError(
            f"body_a must be <= {Config.MAX_BODY_LENGTH} characters"
        )
    if cleaned["body_b"] and len(cleaned["body_b"]) > Config.MAX_BODY_LENGTH:
        raise ValueError(
            f"body_b must be <= {Config.MAX_BODY_LENGTH} characters"
        )

    # --- Template type ----------------------------------------------------
    template_type = cleaned["template_type"]
    if template_type not in (TEMPLATE_SINGLE, TEMPLATE_AB):
        raise ValueError(
            f"template_type must be '{TEMPLATE_SINGLE}' or '{TEMPLATE_AB}'"
        )
    if template_type == TEMPLATE_AB and not cleaned["body_b"]:
        raise ValueError("template_type 'ab' requires a non-empty body_b")

    # --- Ethics validators ------------------------------------------------
    if not is_sender_fictional(cleaned["sender_name"]):
        raise ValueError(
            "sender_name looks like a real brand; use a clearly fictional "
            "name (e.g., 'Demo Co.', 'Acme Internal IT')"
        )
    if not is_template_safe(cleaned["body_a"]):
        raise ValueError("body_a mentions a real brand")
    if cleaned["body_b"] and not is_template_safe(cleaned["body_b"]):
        raise ValueError("body_b mentions a real brand")
    if not is_landing_link_local(cleaned["landing_path"]):
        raise ValueError(
            "landing_path must be a local route under /landing/..."
        )

    return models.insert_campaign(cleaned)


def get_campaign(campaign_id: int) -> Optional[dict]:
    """Return one campaign by ID, or ``None`` if not found."""
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("campaign_id must be an integer") from exc
    return models.get_campaign_by_id(cid)


def list_campaigns() -> list[dict]:
    """Return all campaigns ordered newest first."""
    return models.list_campaigns()


# --- Demo seeding -----------------------------------------------------------
#
# Used only when DEMO_MODE is on. Populates an empty database with two
# campaigns and a believable funnel so the dashboard is worth showing
# with a single command. All copy below is deliberately fictional and
# brand-safe (it must pass is_sender_fictional / is_template_safe).

_DEMO_SINGLE = {
    "title": "Demo - Quarterly Password Reset",
    "sender_name": "Demo Co. IT",
    "subject": "Action needed: reset your demo account password",
    "body_a": (
        "Hello,\n\nOur records show your demo account password expires "
        "today. Use the button below to set a new one and keep your "
        "access active.\n\nThanks,\nDemo Co. IT Helpdesk"
    ),
    "cta_text": "Reset my password",
    "landing_path": "/landing/1",
    "template_type": "single",
}

_DEMO_AB = {
    "title": "Demo - Mailbox Storage Warning (A/B)",
    "sender_name": "Acme Internal",
    "subject": "Your mailbox is almost full",
    "body_a": (
        "Hi,\n\nYour mailbox has reached 90% of its quota. Review your "
        "storage settings to avoid missing new messages.\n\nAcme Internal"
    ),
    "body_b": (
        "URGENT: Your mailbox is FULL and incoming mail is being rejected "
        "right now. Act immediately to restore delivery.\n\nAcme Internal"
    ),
    "cta_text": "Review storage",
    "landing_path": "/landing/2",
    "template_type": "ab",
}


def seed_demo_campaigns() -> list[int]:
    """Seed two demo campaigns plus a sample funnel into an empty database.

    Idempotent: if any campaign already exists this is a no-op and returns
    an empty list. Routes inserts through ``create_campaign`` so the demo
    data is held to the same ethics rules as user-authored campaigns.

    The hard-coded landing paths (``/landing/1`` and ``/landing/2``) rely on
    the empty-table precondition: with no rows, AUTOINCREMENT assigns ids
    1 and 2 to the two campaigns created here.
    """
    if models.list_campaigns():
        return []

    single_id = create_campaign(dict(_DEMO_SINGLE))
    ab_id = create_campaign(dict(_DEMO_AB))
    _seed_demo_funnel(single_id, ab=False)
    _seed_demo_funnel(ab_id, ab=True)
    return [single_id, ab_id]


def _seed_demo_funnel(campaign_id: int, ab: bool) -> None:
    """Record a believable funnel of events for one seeded campaign.

    Every write goes through the Logging service (the only events writer),
    so dedup, the payload guard, and the allow-list all apply to seed data
    too. The Logging service is imported lazily to keep the
    campaign -> logging dependency one-directional at module import time.
    """
    from app.constants import (
        EVENT_FAKE_SUBMIT_ATTEMPTED,
        EVENT_FORM_INTERACTION_STARTED,
        EVENT_LANDING_EXITED,
        EVENT_LANDING_VISITED,
        EVENT_LINK_CLICKED,
        EVENT_MESSAGE_OPENED,
    )
    from app.logging_mod import service as logging_service

    def funnel(variant, opened, clicked, interacted, submitted, exited):
        for sc in opened:
            logging_service.record_event(
                EVENT_MESSAGE_OPENED, campaign_id, sc, variant
            )
        for sc in clicked:
            logging_service.record_event(
                EVENT_LINK_CLICKED, campaign_id, sc, variant
            )
            logging_service.record_event(
                EVENT_LANDING_VISITED, campaign_id, sc, variant
            )
        for sc in interacted:
            logging_service.record_event(
                EVENT_FORM_INTERACTION_STARTED, campaign_id, sc, variant
            )
        for sc in submitted:
            logging_service.record_event(
                EVENT_FAKE_SUBMIT_ATTEMPTED, campaign_id, sc, variant,
                metadata={"field_count": 2},
            )
        for sc, ms in exited:
            logging_service.record_event(
                EVENT_LANDING_EXITED, campaign_id, sc, variant,
                metadata={"time_on_page_ms": ms},
            )

    if not ab:
        s = [f"demo-{i:02d}" for i in range(1, 9)]  # demo-01 .. demo-08
        funnel(
            "A",
            opened=s,            # 8 open
            clicked=s[:5],       # 5 click + visit
            interacted=s[:3],    # 3 start the form
            submitted=s[:2],     # 2 submit
            exited=[(s[0], 8200), (s[1], 5400)],
        )
    else:
        a = ["demo-01", "demo-03", "demo-05", "demo-07"]
        b = ["demo-02", "demo-04", "demo-06", "demo-08"]
        # Variant A converts better than B, so the A/B chart shows a gap.
        funnel(
            "A",
            opened=a,            # 4 open
            clicked=a[:3],       # 3 click + visit
            interacted=a[:2],    # 2 start the form
            submitted=a[:2],     # 2 submit
            exited=[(a[0], 9100)],
        )
        funnel(
            "B",
            opened=b,            # 4 open
            clicked=b[:1],       # 1 click + visit
            interacted=b[:1],    # 1 starts the form
            submitted=[],        # 0 submit
            exited=[(b[0], 3300)],
        )
