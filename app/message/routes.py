"""HTTP routes for the simulated message.

* ``GET /message/<id>/preview`` — instructor preview, no logging
* ``GET /message/<id>/view``    — subject view; ``message_opened`` will
  be emitted by ``render_context`` in a later commit (commit 7).
"""

from flask import Blueprint, abort, render_template, request

from app.message import service


bp = Blueprint("message", __name__, url_prefix="/message")


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
