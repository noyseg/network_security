"""End-to-end browser test of the full subject funnel.

Drives a real Chromium browser through the entire flow — author a
campaign, view it as a subject, click the lure, submit the fake login,
reach the debrief, and read the dashboard — then asserts both that the
funnel numbers render in the dashboard UI and that nothing resembling the
typed credentials is ever stored.

Requires the optional e2e dependencies (kept out of the core install):

    pip install -r requirements-e2e.txt
    playwright install chromium
    pytest tests/e2e

If Playwright is not installed, this module is skipped, so the default
``pytest`` run stays green and dependency-light.
"""

import json
import re
import sqlite3

import pytest

pytest.importorskip("pytest_playwright")

from playwright.sync_api import Page, expect  # noqa: E402


SUBJECT = "subject-e2e"
FAKE_USERNAME = "victim@example.com"
FAKE_PASSWORD = "Sup3rSecretPassw0rd!"


def _events(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT event_type, metadata_json FROM events"
        ).fetchall()
    finally:
        conn.close()


def test_full_funnel_end_to_end(live_server, page: Page):
    base = live_server["url"]

    # 1. Author a campaign through the admin form. A fresh e2e DB means
    #    this becomes campaign id 1.
    page.goto(f"{base}/admin/campaigns/new")
    page.fill("input[name=title]", "E2E Demo Campaign")
    page.fill("input[name=sender_name]", "Demo Co. IT")
    page.fill("input[name=subject]", "Action needed on your demo account")
    page.fill(
        "textarea[name=body_a]",
        "Please review your account using the link below.",
    )
    page.fill("input[name=cta_text]", "Review account")
    page.fill("input[name=landing_path]", "/landing/1")
    page.select_option("select[name=template_type]", "single")
    page.click("button[type=submit]")

    expect(page).to_have_url(f"{base}/admin/campaigns/1")
    expect(page.locator("h1")).to_contain_text("E2E Demo Campaign")

    # 2. Open the message as a subject (records message_opened).
    page.goto(f"{base}/message/1/view?subject={SUBJECT}")
    expect(page.locator(".sim-banner")).to_be_visible()

    # 3. Click the lure -> fake login page (records link_clicked + landing_visited).
    page.click(".message-cta a.button")
    expect(page).to_have_url(re.compile(r"/landing/1\b"))
    expect(page.locator("#fake-login-form")).to_be_visible()

    # 4. Type fake credentials and submit. tracker.js sends ONLY a field count.
    page.fill("input[name=username]", FAKE_USERNAME)
    page.fill("input[name=password]", FAKE_PASSWORD)
    page.click("#fake-login-form button[type=submit]")

    # 5. Redirected to the educational debrief page.
    page.wait_for_url("**/landing/debrief**")
    expect(page.locator("h1")).to_contain_text("What just happened")

    # 6. The dashboard renders the funnel numbers from the recorded events.
    page.goto(f"{base}/admin/dashboard/1")
    expect(page.locator("#tile-opens")).to_have_text("1")
    expect(page.locator("#tile-clicks")).to_have_text("1")
    expect(page.locator("#tile-visits")).to_have_text("1")
    expect(page.locator("#tile-submits")).to_have_text("1")

    # 7. Ethics guarantee: nothing the user typed reaches the database.
    rows = _events(live_server["db_path"])
    assert rows, "expected the funnel to have produced events"
    for event_type, meta in rows:
        if not meta:
            continue
        assert FAKE_PASSWORD not in meta, (
            f"password leaked into events.metadata_json ({event_type}): {meta}"
        )
        assert FAKE_USERNAME not in meta, (
            f"username leaked into events.metadata_json ({event_type}): {meta}"
        )
        for key, value in json.loads(meta).items():
            assert not isinstance(value, str), (
                f"unexpected string value in metadata under {key!r}: {value!r}"
            )
