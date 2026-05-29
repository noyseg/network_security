"""HTTP routes for the landing module.

* ``GET  /landing/<id>``         — fake login page; emits link_clicked +
  landing_visited server-side.
* ``GET  /landing/<id>/preview`` — admin preview of the fake login page;
  side-effect free (no events, no tracker.js).
* ``POST /landing/<id>/submit``  — safe submit; accepts only
  ``{subject_code, variant, field_count}``. The endpoint itself cannot
  receive field names or values.
* ``GET  /landing/debrief``      — educational debrief page.
"""

from flask import Blueprint, jsonify, render_template, request

from app.campaign import service as campaign_service
from app.constants import (
    EVENT_LANDING_VISITED,
    EVENT_LINK_CLICKED,
    TEMPLATE_SINGLE,
    VARIANT_A,
    VARIANT_B,
)
from app.landing import service
from app.logging_mod import service as logging_service
from app.validators import is_valid_subject_code


bp = Blueprint("landing", __name__, url_prefix="/landing")


@bp.get("/<int:campaign_id>")
def landing_page(campaign_id: int):
    subject_code = (request.args.get("subject") or "").strip()
    variant = (request.args.get("variant") or "").strip()

    if not subject_code:
        return "missing required query parameter: subject", 400
    if not is_valid_subject_code(subject_code):
        return "invalid subject code", 400

    campaign = campaign_service.get_campaign(campaign_id)
    if campaign is None:
        return f"campaign {campaign_id} not found", 404

    if not variant:
        if campaign["template_type"] == TEMPLATE_SINGLE:
            variant = VARIANT_A
        else:
            return "missing required query parameter: variant", 400

    try:
        logging_service.record_event(
            EVENT_LINK_CLICKED, campaign_id, subject_code, variant
        )
        logging_service.record_event(
            EVENT_LANDING_VISITED, campaign_id, subject_code, variant
        )
    except ValueError as exc:
        return str(exc), 400

    return render_template(
        "landing/fake_login.html",
        campaign_id=campaign_id,
        subject_code=subject_code,
        variant=variant,
    )


@bp.get("/<int:campaign_id>/preview")
def landing_preview(campaign_id: int):
    """Admin preview of the fake login page exactly as a subject sees it.

    Side-effect free: records no events and loads no tracker.js, so an
    instructor can inspect the lure without polluting the funnel data.
    """
    campaign = campaign_service.get_campaign(campaign_id)
    if campaign is None:
        return f"campaign {campaign_id} not found", 404

    variant = (request.args.get("variant") or "").strip().upper()
    if variant not in (VARIANT_A, VARIANT_B):
        variant = VARIANT_A
    if campaign["template_type"] == TEMPLATE_SINGLE:
        variant = VARIANT_A

    return render_template(
        "landing/fake_login.html",
        campaign_id=campaign_id,
        subject_code="",
        variant=variant,
        preview=True,
    )


@bp.post("/<int:campaign_id>/submit")
def submit(campaign_id: int):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(ok=False, error="body must be a JSON object"), 400

    subject_code = str(payload.get("subject_code", "")).strip()
    variant = str(payload.get("variant", "")).strip()
    field_count_raw = payload.get("field_count")

    try:
        field_count = int(field_count_raw)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="field_count must be an integer"), 400

    try:
        redirect_url = service.handle_fake_submit(
            campaign_id, subject_code, variant, field_count
        )
    except (TypeError, ValueError) as exc:
        return jsonify(ok=False, error=str(exc)), 400

    return jsonify(ok=True, redirect=redirect_url), 200


@bp.get("/debrief")
def debrief():
    subject_code = (request.args.get("subject") or "").strip()
    variant = (request.args.get("variant") or "").strip()
    campaign_id_raw = (request.args.get("campaign_id") or "").strip()
    try:
        campaign_id = int(campaign_id_raw) if campaign_id_raw else 0
    except ValueError:
        campaign_id = 0
    # Only pass identifiers through when all three are present and the
    # subject code is well-formed. Otherwise the page still renders, but
    # tracker.js will no-op (no exit ping) because hasIdentifiers fails.
    if not (campaign_id > 0 and is_valid_subject_code(subject_code) and variant):
        campaign_id = 0
        subject_code = ""
        variant = ""
    return render_template(
        "landing/debrief.html",
        campaign_id=campaign_id,
        subject_code=subject_code,
        variant=variant,
    )
