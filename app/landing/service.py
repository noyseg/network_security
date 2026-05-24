"""Landing service.

Owns the safe submit logic for the fake login page. The function
signature itself forbids receiving field names or values — only an
integer count of inputs on the form.
"""

from urllib.parse import urlencode

from app.constants import EVENT_FAKE_SUBMIT_ATTEMPTED
from app.logging_mod import service as logging_service


MAX_FIELD_COUNT = 20
DEBRIEF_PATH = "/landing/debrief"


def handle_fake_submit(
    campaign_id: int,
    subject_code: str,
    variant: str,
    field_count: int,
) -> str:
    """Record a fake-submit attempt and return the debrief URL.

    Raises ``ValueError`` for any invalid input. By design, the parameter
    list cannot accept field names or field values — only a count.
    """
    if not isinstance(field_count, int) or isinstance(field_count, bool):
        raise ValueError("field_count must be an integer")
    if field_count < 0 or field_count > MAX_FIELD_COUNT:
        raise ValueError(
            f"field_count must be in [0, {MAX_FIELD_COUNT}]; got {field_count}"
        )

    logging_service.record_event(
        EVENT_FAKE_SUBMIT_ATTEMPTED,
        int(campaign_id),
        subject_code,
        variant,
        metadata={"field_count": field_count},
    )

    query = urlencode({
        "campaign_id": int(campaign_id),
        "subject": subject_code,
        "variant": variant,
    })
    return f"{DEBRIEF_PATH}?{query}"
