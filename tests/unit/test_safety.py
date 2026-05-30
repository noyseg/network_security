"""Ethics / safety pinning tests.

These tests are the executable form of the project's hard rules. They
fail loudly if a regression ever lets a non-fictional sender land in
the database, a non-local landing path slip through, an unknown event
type get recorded, an outbound-HTTP library appear in the codebase, or
the server bind to anything other than localhost.

Scope: every test in this file is a *project-wide invariant*, not a
function-level unit test. They are deliberately separate from
``test_validators.py`` (which tests the validators themselves).
"""

import os
import re

from config import Config


# ---------------------------------------------------------------------------
# Codebase-scan tests (no app fixture needed)
# ---------------------------------------------------------------------------


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
APP_DIR = os.path.join(PROJECT_ROOT, "app")
RUN_PY = os.path.join(PROJECT_ROOT, "run.py")


def _walk_python_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip caches.
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


class TestNoOutboundHttp:
    """The codebase must not import any library that opens external HTTP."""

    FORBIDDEN_PATTERNS = (
        re.compile(r"^\s*import\s+requests\b", re.MULTILINE),
        re.compile(r"^\s*from\s+requests\b", re.MULTILINE),
        re.compile(r"^\s*import\s+httpx\b", re.MULTILINE),
        re.compile(r"^\s*from\s+httpx\b", re.MULTILINE),
        re.compile(r"^\s*import\s+urllib\.request\b", re.MULTILINE),
        re.compile(r"^\s*from\s+urllib\.request\b", re.MULTILINE),
        re.compile(r"^\s*import\s+http\.client\b", re.MULTILINE),
        re.compile(r"^\s*from\s+http\.client\b", re.MULTILINE),
    )

    def test_no_outbound_http_imports_in_app(self):
        offenders = []
        for path in _walk_python_files(APP_DIR):
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            for pat in self.FORBIDDEN_PATTERNS:
                if pat.search(text):
                    offenders.append((path, pat.pattern))
        assert not offenders, (
            f"Outbound-HTTP imports found in the codebase: {offenders}"
        )


class TestServerBindsLocally:
    """``run.py`` must bind to 127.0.0.1, and only 127.0.0.1."""

    def test_config_host_is_localhost(self):
        assert Config.HOST == "127.0.0.1"

    def test_run_py_uses_config_host(self):
        with open(RUN_PY, "r", encoding="utf-8") as fh:
            text = fh.read()
        # Must reference Config.HOST when starting the server.
        assert "Config.HOST" in text, (
            "run.py should pass Config.HOST to app.run()"
        )
        # And must NOT contain a hard-coded bind to anywhere else.
        assert "0.0.0.0" not in text, (
            "run.py contains the wildcard bind 0.0.0.0 — not allowed"
        )


# ---------------------------------------------------------------------------
# Schema-scan tests (need a populated DB)
# ---------------------------------------------------------------------------


def _make_campaign(client, sender="Demo Co.", landing="/landing/1"):
    r = client.post("/admin/campaigns", data={
        "title": "Safety test campaign",
        "sender_name": sender,
        "subject": "Action required",
        "body_a": "Click below to confirm.",
        "body_b": "",
        "cta_text": "Confirm",
        "landing_path": landing,
        "template_type": "single",
    })
    assert r.status_code == 302, (
        f"campaign create failed: {r.status_code} {r.data!r}"
    )
    return int(r.headers["Location"].rstrip("/").rsplit("/", 1)[-1])


def _all_campaigns(app):
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        return [dict(r) for r in conn.execute(
            "SELECT id, sender_name, landing_path FROM campaigns"
        ).fetchall()]


def _all_event_types(app):
    from app import db as db_module
    with app.app_context():
        conn = db_module.get_connection()
        return [r["event_type"] for r in conn.execute(
            "SELECT event_type FROM events"
        ).fetchall()]


class TestLandingPathMustBeLocal:
    """Every campaign row's landing_path must pass the local-link validator."""

    def test_seeded_campaigns_all_pass_validator(self, app, client):
        from app.validators import is_landing_link_local
        _make_campaign(client, landing="/landing/1")
        _make_campaign(client, landing="/landing/2")
        for row in _all_campaigns(app):
            assert is_landing_link_local(row["landing_path"]), (
                f"campaign {row['id']} has non-local landing_path: "
                f"{row['landing_path']!r}"
            )

    def test_create_with_external_landing_rejected(self, client):
        r = client.post("/admin/campaigns", data={
            "title": "Bad",
            "sender_name": "Demo Co.",
            "subject": "x",
            "body_a": "x",
            "body_b": "",
            "cta_text": "x",
            "landing_path": "https://evil.example.com/login",
            "template_type": "single",
        })
        assert r.status_code == 400


class TestSenderMustBeFictional:
    """Every campaign row's sender_name must pass the fictional-sender check."""

    def test_seeded_campaigns_all_pass_validator(self, app, client):
        from app.validators import is_sender_fictional
        _make_campaign(client, sender="Demo Co.")
        _make_campaign(client, sender="Acme Internal IT")
        for row in _all_campaigns(app):
            assert is_sender_fictional(row["sender_name"]), (
                f"campaign {row['id']} has non-fictional sender_name: "
                f"{row['sender_name']!r}"
            )

    def test_create_with_real_brand_rejected(self, client):
        r = client.post("/admin/campaigns", data={
            "title": "Bad",
            "sender_name": "Bank of America",
            "subject": "x",
            "body_a": "x",
            "body_b": "",
            "cta_text": "x",
            "landing_path": "/landing/1",
            "template_type": "single",
        })
        assert r.status_code == 400


class TestEventTypesAreAllowListed:
    """Every events row must have an event_type in the closed allow-list."""

    def test_recorded_events_all_pass_allow_list(self, app, client):
        cid = _make_campaign(client)
        # Drive every event type that record_event accepts from the
        # outside via the existing routes.
        client.get(f"/message/{cid}/view?subject=subject-01")
        client.get(f"/landing/{cid}?subject=subject-01&variant=A")
        client.post(
            f"/landing/{cid}/submit",
            json={"subject_code": "subject-01", "variant": "A", "field_count": 2},
        )
        client.post("/events/ping", json={
            "event_type": "form_interaction_started",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
        })
        client.post("/events/ping", json={
            "event_type": "landing_exited",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
            "metadata": {"time_on_page_ms": 1234},
        })

        recorded = _all_event_types(app)
        assert recorded, "expected at least one event row from the flow"
        for et in recorded:
            assert et in Config.ALLOWED_EVENT_TYPES, (
                f"event_type {et!r} is not in the allow-list "
                f"{Config.ALLOWED_EVENT_TYPES}"
            )

    def test_ping_with_unknown_event_type_rejected(self, client):
        cid = _make_campaign(client)
        r = client.post("/events/ping", json={
            "event_type": "totally_made_up",
            "campaign_id": cid,
            "subject_code": "subject-01",
            "variant": "A",
        })
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Constants-level invariant
# ---------------------------------------------------------------------------


class TestAllowedEventTypesMatchesConstants:
    """``Config.ALLOWED_EVENT_TYPES`` and the per-event constants module
    should agree — drift between them would let an unknown event slip
    through one validator while still passing the other."""

    def test_constants_are_subset_of_config(self):
        from app import constants as C
        named = {
            C.EVENT_MESSAGE_OPENED,
            C.EVENT_LINK_CLICKED,
            C.EVENT_LANDING_VISITED,
            C.EVENT_FORM_INTERACTION_STARTED,
            C.EVENT_FAKE_SUBMIT_ATTEMPTED,
            C.EVENT_LANDING_EXITED,
        }
        assert named == set(Config.ALLOWED_EVENT_TYPES)


class TestMailDefaultsSafe:
    """The mail layer must be safe-by-default: no real send unless explicitly
    opted in via configuration. Real sending is an authorized opt-in only;
    everything else stays sandboxed."""

    def test_default_mail_mode_is_sandbox(self):
        assert Config.MAIL_MODE == "sandbox"

    def test_get_mail_sender_defaults_to_sandbox(self):
        from app.mail.service import SandboxMailSender, get_mail_sender
        assert isinstance(get_mail_sender(1), SandboxMailSender)
