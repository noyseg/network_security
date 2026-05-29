# Final Report — Controlled Phishing Simulation Platform

**Course:** Network Security — Mini-Project
**Authors:** Noy Segal, Noam Tamari

This report consolidates the design and the reasoning behind the project. It
is intentionally a summary; the authoritative documents are `PLANNING.md`
(high-level report) and `IMPLEMENTATION_PLAN.md` (code-level plan). This file
does not duplicate them — it ties them together and records what was built.

## 1. What we built

A local, closed-environment web platform that simulates a phishing campaign
end-to-end for **education and awareness** — never for real attacks. An
instructor creates a campaign with a fictional sender and a fictional landing
page, "sends" it only by rendering it in the developer's own browser, and
watches a behavioral funnel form as a pseudonymous test subject opens the
message, clicks the link, reaches a fake login page, and (optionally) submits
it. The platform records the funnel as **safe events only** and visualizes it
on a dashboard, including an A/B comparison between two message variants.

No real email is ever sent, no real organization is impersonated, and no real
credential is ever stored.

## 2. Architecture

Three tiers: a Flask backend, server-rendered Jinja templates with two small
vanilla-JS modules, and a local SQLite database. The backend is five feature
modules plus a thin infrastructure layer:

| Module | Responsibility |
|--------|----------------|
| Campaign | Create / list / read campaigns; validate authoring input; DEMO_MODE seeder |
| Message | Render the simulated message; pick the A/B variant; emit `message_opened` |
| Landing | Fake login page, safe submit endpoint, educational debrief |
| Logging | `record_event` — the **only** writer of the `events` table |
| Dashboard | Aggregate events into funnel + per-variant numbers (read-only) |
| Infrastructure | App factory, config, DB layer, validators, constants |

Call direction is strictly one-way: **Browser → Routes → Services → Models →
SQLite**. Routes never touch SQL directly; only `app/models.py` issues SQL.
The Logging service is the sole writer of events; the Dashboard service is the
sole aggregate reader. The frontend talks to the backend only over HTTP — full
page loads plus JSON event pings from `tracker.js`.

```
Browser ──HTTP/fetch──> Routes ──> Services ──> Models ──> SQLite
                     (campaign/message/landing/logging/dashboard)
```

### Data model

Three tables: `campaigns`, `subjects` (pseudonymous labels), and `events`
(the funnel). Dedup-once events (`message_opened`, `link_clicked`,
`landing_visited`, `form_interaction_started`) are kept unique per
`(campaign, subject)` by a partial UNIQUE index **and** an application-layer
check, so the dashboard's "count distinct subjects" math is always correct.
`fake_submit_attempted` may repeat; `landing_exited` is updated in place
(latest wins). See `IMPLEMENTATION_PLAN.md` §5 and §8.4.

## 3. The five ethical rules and how each is enforced

The project is built around five hard rules. Each is enforced in **code** and
pinned by a **test** so a regression fails loudly.

1. **Local / lab only.** `run.py` binds to `Config.HOST = "127.0.0.1"`.
   Pinned by `test_safety.py::TestServerBindsLocally`.
2. **No real organizations.** `is_sender_fictional` / `is_template_safe`
   (`app/validators.py`) check sender names and bodies against
   `Config.DISALLOWED_BRANDS` before a campaign can be saved. Pinned by
   `test_validators.py` and `test_safety.py::TestSenderMustBeFictional`.
3. **No real users.** Subjects are pseudonymous labels validated by
   `is_valid_subject_code`; the landing-path validator
   (`is_landing_link_local`) accepts only local `/landing/` routes. Pinned by
   `test_safety.py::TestLandingPathMustBeLocal`.
4. **No real passwords.** The submit endpoint and `handle_fake_submit` accept
   only an integer `field_count` — the signature itself cannot receive names
   or values. `tracker.js` sends only the input *count*. Pinned by
   `test_landing_flow.py` and `test_no_credentials_stored.py`, which scans the
   SQLite file for any string value that looks like a credential.
5. **Safe logging only.** `record_event` enforces the event-type allow-list
   and runs `assert_no_credential_payload` on every write. Pinned by
   `test_safety.py::TestEventTypesAreAllowListed` and the credential scan.

A codebase scan (`test_safety.py::TestNoOutboundHttp`) additionally asserts no
outbound-HTTP library (`requests`, `httpx`, `urllib.request`, `http.client`)
is imported anywhere in `app/` — the system cannot phone home.

## 4. Metrics the dashboard produces

`GET /admin/dashboard/<id>/data` returns `{campaign, totals, variants}`.
`totals` (and each of `variants.A` / `variants.B`) contains:

- `opens`, `clicks`, `visits`, `submits` — distinct-subject counts (the funnel).
- `click_rate` = clicks / opens, `submit_rate` = submits / opens (0 when opens = 0).
- `avg_response_time_ms` — mean per-subject gap between first `message_opened`
  and first `link_clicked`.
- `avg_time_on_page_ms` — mean per-subject gap between first `landing_visited`
  and the latest `landing_exited` (falling back to `fake_submit_attempted`).

The dashboard renders three Chart.js views: a funnel bar
(opens → clicks → visits → submits), an A-vs-B grouped bar (click rate +
submit rate), and two summary tiles (avg response time, avg time on page).
A zero-data campaign renders cleanly with all values at 0.

## 5. Testing

The suite runs against a fresh temporary SQLite database per session and is
green. It covers: validator unit tests; the dashboard aggregation service;
per-route integration flows (campaign / message / landing / logging /
dashboard); the DEMO_MODE seeder; and the ethics/safety assertions described
in §3. Run `pytest`, or `pytest -k safety` for just the ethical guards.

## 6. Reproducing the demo

```
DEMO_MODE=1 python run.py      # or set $env:DEMO_MODE on Windows
```

Then open `/admin/dashboard/1` (single-template campaign) and
`/admin/dashboard/2` (A/B campaign) to see populated funnels. Screenshots of
each user-flow step belong in `docs/screenshots/` — see `CAPTURE_LIST.md`.

## 7. Future work

Out of scope for this mini-project but natural extensions (see `PLANNING.md`
§10): a per-subject risk score, a curated template library, an SMS/smishing
variant, a safe CSV export, admin authentication, and Hebrew/English
multi-language templates. The modular design keeps these cheap to add because
each reuses the existing module interfaces.
