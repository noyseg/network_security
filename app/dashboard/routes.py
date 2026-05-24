"""HTTP routes for the dashboard.

* ``GET /admin/dashboard/<id>``       — HTML shell with Chart.js loaded
* ``GET /admin/dashboard/<id>/data``  — JSON for the charts:
    ``{campaign, totals, variants}``
"""

from flask import Blueprint, abort, jsonify, render_template

from app.campaign import service as campaign_service
from app.dashboard import service as dashboard_service


bp = Blueprint("dashboard", __name__, url_prefix="/admin/dashboard")


@bp.get("/<int:campaign_id>")
def view(campaign_id: int):
    campaign = campaign_service.get_campaign(campaign_id)
    if campaign is None:
        abort(404, description=f"campaign {campaign_id} not found")
    return render_template("admin/dashboard.html", campaign=campaign)


@bp.get("/<int:campaign_id>/data")
def data(campaign_id: int):
    campaign = campaign_service.get_campaign(campaign_id)
    if campaign is None:
        return jsonify(error=f"campaign {campaign_id} not found"), 404
    try:
        totals = dashboard_service.aggregate_campaign(campaign_id)
        variants = dashboard_service.compare_variants(campaign_id)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(campaign=campaign, totals=totals, variants=variants)
