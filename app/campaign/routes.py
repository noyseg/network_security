"""Admin HTTP routes for campaigns.

Mounted at ``/admin`` so admin URLs read naturally:

* ``GET  /admin/campaigns``                     — list
* ``GET  /admin/campaigns/new``                 — authoring form
* ``POST /admin/campaigns``                     — create
* ``GET  /admin/campaigns/<id>``                — detail (incl. recipients)
* ``POST /admin/campaigns/<id>/recipients``     — save recipient list
* ``POST /admin/campaigns/<id>/send-test``      — send the simulated email
"""

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from app.campaign import service


bp = Blueprint("campaign", __name__, url_prefix="/admin")


def _not_found(campaign_id: int):
    return (
        render_template(
            "admin/campaign_list.html",
            campaigns=service.list_campaigns(),
            error=f"Campaign {campaign_id} not found.",
        ),
        404,
    )


@bp.get("/campaigns")
def list_view():
    campaigns = service.list_campaigns()
    return render_template("admin/campaign_list.html", campaigns=campaigns)


@bp.get("/campaigns/new")
def new_form():
    return render_template(
        "admin/campaign_new.html", errors=[], previous={}
    )


@bp.post("/campaigns")
def create():
    payload = {
        "title": request.form.get("title", ""),
        "sender_name": request.form.get("sender_name", ""),
        "subject": request.form.get("subject", ""),
        "body_a": request.form.get("body_a", ""),
        "body_b": request.form.get("body_b", ""),
        "cta_text": request.form.get("cta_text", ""),
        "landing_path": request.form.get("landing_path", ""),
        "template_type": request.form.get("template_type", "single"),
    }
    try:
        new_id = service.create_campaign(payload)
    except ValueError as exc:
        return (
            render_template(
                "admin/campaign_new.html",
                errors=[str(exc)],
                previous=payload,
            ),
            400,
        )

    return redirect(url_for("campaign.detail", campaign_id=new_id))


@bp.get("/campaigns/<int:campaign_id>")
def detail(campaign_id: int):
    campaign = service.get_campaign(campaign_id)
    if campaign is None:
        return _not_found(campaign_id)
    return render_template(
        "admin/campaign_detail.html",
        campaign=campaign,
        recipients_text="\n".join(campaign["recipients"]),
    )


@bp.post("/campaigns/<int:campaign_id>/recipients")
def update_recipients(campaign_id: int):
    raw = request.form.get("recipients", "")
    campaign = service.get_campaign(campaign_id)
    if campaign is None:
        return _not_found(campaign_id)
    try:
        saved = service.set_recipients(campaign_id, raw)
    except ValueError as exc:
        return (
            render_template(
                "admin/campaign_detail.html",
                campaign=campaign,
                recipients_text=raw,  # keep what the user typed so they can fix it
                recipients_error=str(exc),
            ),
            400,
        )
    campaign = service.get_campaign(campaign_id)  # reload persisted list
    return render_template(
        "admin/campaign_detail.html",
        campaign=campaign,
        recipients_text="\n".join(saved),
        recipients_saved=f"Saved {len(saved)} recipient(s).",
    )


@bp.post("/campaigns/<int:campaign_id>/send-test")
def send_test(campaign_id: int):
    # Lazy import keeps the mail layer (and its optional smtp path) out of
    # module import time.
    from app.mail import service as mail_service

    try:
        summary = mail_service.send_test_email(campaign_id)
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, summary=summary), 200
