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
