"""HTTP routes for the simulated message.

* ``GET /message/<id>/preview`` — instructor preview, no logging
* ``GET /message/<id>/view``    — subject view; emits ``message_opened``
* ``GET /message/<id>/pixel``   — 1x1 PNG that also emits ``message_opened``
  when loaded with a ``subject`` query param. Same dedup target as the
  view route, so loading both for one subject still produces one row.
"""

from flask import Blueprint, Response, abort, render_template, request

from app.constants import EVENT_MESSAGE_OPENED
from app.logging_mod import service as logging_service
from app.message import service


bp = Blueprint("message", __name__, url_prefix="/message")


# Minimal valid 1x1 transparent PNG (67 bytes). Served by the pixel
# route so the simulated message can embed a tracking image without
# pulling in Pillow or a static asset.
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _template_for(variant: str) -> str:
    """Map a variant code to its Jinja template path."""
    return "message/template_b.html" if variant == "B" else "message/template_a.html"


@bp.get("/<int:campaign_id>/preview")
def preview(campaign_id: int):
    variant_override = request.args.get("variant")
    try:
        ctx = service.render_context(
            campaign_id,
            variant=variant_override,
            preview=True,
        )
    except ValueError as exc:
        return str(exc), 400
    if ctx is None:
        abort(404, description=f"campaign {campaign_id} not found")
    return render_template(_template_for(ctx["variant"]), **ctx)


@bp.get("/<int:campaign_id>/view")
def subject_view(campaign_id: int):
    subject_code = (request.args.get("subject") or "").strip()
    if not subject_code:
        return "missing required query parameter: subject", 400
    try:
        ctx = service.render_context(
            campaign_id,
            subject_code=subject_code,
            preview=False,
        )
    except ValueError as exc:
        return str(exc), 400
    if ctx is None:
        abort(404, description=f"campaign {campaign_id} not found")
    return render_template(_template_for(ctx["variant"]), **ctx)


@bp.get("/<int:campaign_id>/pixel")
def pixel(campaign_id: int):
    subject_code = (request.args.get("subject") or "").strip()
    variant = (request.args.get("variant") or "A").strip() or "A"
    if subject_code:
        try:
            logging_service.record_event(
                EVENT_MESSAGE_OPENED,
                campaign_id,
                subject_code,
                variant,
            )
        except ValueError:
            # Never fail the pixel — the image must always render so the
            # embedding page is not visibly broken.
            pass
    return Response(_PNG_1x1, mimetype="image/png")
