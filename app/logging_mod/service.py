"""Logging service.

The only writer of the ``events`` table. Every other backend module
routes event creation through ``record_event`` so that the event-type
allow-list, the sensitive-payload guard, and the deduplication rules
are enforced in exactly one place.

Defense in depth for the four dedup-once event types (message_opened,
link_clicked, landing_visited, form_interaction_started):

1. Application layer  — ``find_event`` lookup before insert.
2. Database layer     — partial UNIQUE index ``uq_events_dedup_once``.
3. Application catch  — ``sqlite3.IntegrityError`` is caught and
                        translated into "row already existed".

``landing_exited`` is updated in place rather than inserted twice;
``fake_submit_attempted`` always inserts a new row (multiple attempts
are meaningful).
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional

from app import models
from app.constants import (
    DEDUP_ONCE_EVENTS,
    EVENT_LANDING_EXITED,
)
from app.validators import (
    assert_no_credential_payload,
    is_allowed_event_type,
    is_valid_subject_code,
)
from config import Config


def record_event(
    event_type: str,
    campaign_id: int,
    subject_code: str,
    variant: str,
    metadata: Optional[dict] = None,
) -> int:
    """Insert one event row (or return an existing one when deduped).

    Validates every argument before any DB write. Returns the integer
    ID of the row that ends up surviving for this
    ``(campaign, subject, event_type)`` triple.

    Raises ``ValueError`` for any rejected input: unknown event type,
    bad variant, unknown campaign, bad subject code, or sensitive
    metadata keys.
    """
    # --- Validate event type --------------------------------------------
    if not is_allowed_event_type(event_type):
        raise ValueError(
            f"event_type '{event_type}' is not in the allow-list"
        )

    # --- Validate variant -----------------------------------------------
    if variant not in Config.ALLOWED_VARIANTS:
        raise ValueError(
            f"variant must be one of {Config.ALLOWED_VARIANTS}; "
            f"got '{variant}'"
        )

    # --- Validate subject_code ------------------------------------------
    if not is_valid_subject_code(subject_code):
        raise ValueError(f"subject_code '{subject_code}' is not valid")

    # --- Validate metadata ----------------------------------------------
    assert_no_credential_payload(metadata)

    # --- Validate campaign exists ---------------------------------------
    if models.get_campaign_by_id(campaign_id) is None:
        raise ValueError(f"campaign {campaign_id} does not exist")

    # --- Resolve subject ------------------------------------------------
    subject_id = models.get_or_create_subject(subject_code)

    # --- Dedup-once events: application-layer check ---------------------
    if event_type in DEDUP_ONCE_EVENTS:
        existing = models.find_event(campaign_id, subject_id, event_type)
        if existing is not None:
            return int(existing["id"])

    metadata_json = json.dumps(metadata) if metadata else None

    # --- landing_exited: update in place if a prior row exists ----------
    if event_type == EVENT_LANDING_EXITED:
        existing = models.find_event(campaign_id, subject_id, event_type)
        if existing is not None:
            models.update_event_metadata(
                int(existing["id"]),
                metadata_json,
                created_at=datetime.utcnow(),
            )
            return int(existing["id"])

    # --- Insert, catching the race-condition path -----------------------
    try:
        return models.insert_event(
            campaign_id=campaign_id,
            subject_id=subject_id,
            variant=variant,
            event_type=event_type,
            metadata_json=metadata_json,
        )
    except sqlite3.IntegrityError:
        # The partial UNIQUE index fired: a concurrent transaction
        # already inserted this dedup-once event between our find_event
        # check and our insert. Treat that row as the surviving one.
        if event_type in DEDUP_ONCE_EVENTS:
            existing = models.find_event(
                campaign_id, subject_id, event_type
            )
            if existing is not None:
                return int(existing["id"])
        raise
