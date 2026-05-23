"""HTTP route for browser-initiated event pings.

The frontend posts JSON to ``/events/ping`` for events that originate
in the browser:

* ``form_interaction_started`` — first focus on any input on the fake
  login form;
* ``landing_exited`` — fired on ``beforeunload`` with
  ``time_on_page_ms``.

Backend routes (the landing page, the pixel, the submit endpoint) call
``record_event`` directly rather than going through this HTTP layer.
"""

from flask import Blueprint, jsonify, request

from app.logging_mod import service


bp = Blueprint("logging_mod", __name__, url_prefix="/events")


@bp.post("/ping")
def ping():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return (
            jsonify(ok=False, error="request body must be a JSON object"),
            400,
        )

    try:
        event_id = service.record_event(
            event_type=str(payload.get("event_type", "")),
            campaign_id=int(payload.get("campaign_id", 0)),
            subject_code=str(payload.get("subject_code", "")),
            variant=str(payload.get("variant", "")),
            metadata=payload.get("metadata"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify(ok=False, error=str(exc)), 400

    return jsonify(ok=True, event_id=event_id), 200
