"""Message service.

Owns the deterministic A/B variant assignment and the rendering context
for the simulated message templates. This module is import-only — it
does not log events. The ``message_opened`` event will be wired into
``render_context`` in a later commit, once the Logging service exists.
"""

import hashlib
from typing import Optional
from urllib.parse import urlencode

from app.campaign import service as campaign_service
from app.constants import TEMPLATE_SINGLE, VARIANT_A, VARIANT_B
from app.validators import is_valid_subject_code


def pick_variant(campaign_id: int, subject_code: str) -> str:
    """Deterministic A/B assignment.

    The same ``(campaign_id, subject_code)`` pair always produces the
    same variant, so a subject re-opening the message sees the same
    content. SHA-256 is overkill but it's stdlib and clearly fair.
    """
    if not subject_code:
        raise ValueError("subject_code must be non-empty")
    key = f"{int(campaign_id)}:{subject_code}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return VARIANT_A if digest[-1] % 2 == 0 else VARIANT_B


def render_context(
    campaign_id: int,
    subject_code: Optional[str] = None,
    variant: Optional[str] = None,
    preview: bool = False,
) -> Optional[dict]:
    """Build the rendering context dict for a message template.

    Returns ``None`` when the campaign does not exist (the route turns
    that into a 404). Returns a populated dict otherwise:

    ``{campaign, variant, body, cta_text, landing_url,
       tracking_pixel_url, preview}``

    Variant selection order:
      1. If the campaign is ``template_type='single'``, force variant A.
      2. Else if an explicit ``variant`` argument is given, honor it
         (used by ``/preview?variant=B``).
      3. Else if ``subject_code`` is given, compute deterministically.
      4. Else (preview without subject) fall back to A.
    """
    campaign = campaign_service.get_campaign(campaign_id)
    if campaign is None:
        return None

    if campaign["template_type"] == TEMPLATE_SINGLE:
        chosen = VARIANT_A
    elif variant in (VARIANT_A, VARIANT_B):
        chosen = variant
    elif subject_code:
        if not is_valid_subject_code(subject_code):
            raise ValueError("subject_code shape is invalid")
        chosen = pick_variant(campaign_id, subject_code)
    else:
        chosen = VARIANT_A

    body = campaign["body_a"] if chosen == VARIANT_A else campaign["body_b"]

    # Landing URL carries the subject + variant so the landing route can
    # log the click for the right pair.
    landing_query = {}
    if subject_code:
        landing_query["subject"] = subject_code
    landing_query["variant"] = chosen
    landing_url = f"{campaign['landing_path']}?{urlencode(landing_query)}"

    # Pixel URL — the actual pixel route lands in a later commit, but
    # the template references this URL so the wiring is ready.
    pixel_query = {"variant": chosen}
    if subject_code:
        pixel_query["subject"] = subject_code
    pixel_url = f"/message/{int(campaign_id)}/pixel?{urlencode(pixel_query)}"

    return {
        "campaign": campaign,
        "variant": chosen,
        "body": body,
        "cta_text": campaign["cta_text"],
        "landing_url": landing_url,
        "tracking_pixel_url": pixel_url,
        "preview": preview,
    }
