# Controlled Phishing Simulation Platform

A **local, lab-only** educational platform for studying the human factor in
network security. The system simulates a phishing campaign end-to-end —
message preview, fake landing page, safe event tracking, dashboard — without
ever sending real email, impersonating a real organization, or collecting real
credentials.

**Course:** Network Security — Mini-Project
**Authors:** Noy Segal, Noam Tamari
**Stack:** Flask + Jinja2 + SQLite + vanilla JS (Chart.js via CDN on the dashboard only).

## Ethical Limits (Hard Rules)

1. **Local / lab use only.** The development server binds to `127.0.0.1`.
2. **No real organizations.** Sender names and template bodies are checked
   against a blocklist of real brands before a campaign can be saved.
3. **No real users in the funnel.** Subjects (the labels written into the
   `events` table) are pseudonymous — never real email addresses. The
   optional per-campaign recipient list (for the "Send test email" action)
   stores internal test addresses locally, but those addresses never enter
   the events table; clicks are still attributed via a derived pseudonymous
   code.
4. **No real passwords.** The fake submit endpoint accepts only an integer
   field count; it cannot receive names or values.
5. **Safe logging only.** Events are limited to a closed allow-list and a
   credential-payload guard runs on every event write.
6. **Safe-by-default mail.** Test-email sending is **sandboxed by default**
   (records to a local outbox, no network). A real SMTP adapter is an
   explicit opt-in for authorized internal training, gated by env config.
   The real `From` is always the configured account — **sender identity is
   never spoofed** — and the landing page still captures nothing but a
   field count.

These rules are encoded in code (`app/validators.py`, the Logging service's
`record_event`, `app/mail/service.py`) and pinned by tests
(`tests/unit/test_validators.py`, `tests/unit/test_safety.py`,
`tests/integration/test_no_credentials_stored.py`,
`tests/integration/test_send_test_email.py`).

## Run It

```
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
python run.py
```

The app starts on `http://127.0.0.1:5000` and creates `data/phishing_sim.sqlite`
on first launch.

### One-command demo (DEMO_MODE)

To start with two campaigns and a pre-populated dashboard already in place:

```
# Windows (PowerShell)
$env:DEMO_MODE = "1"; python run.py

# macOS / Linux
DEMO_MODE=1 python run.py
```

`DEMO_MODE=1` seeds one single-template campaign and one A/B campaign, plus a
realistic funnel of events, **only when the campaigns table is empty** (it is
idempotent — restarting will not duplicate data). It is off by default. Open
`/admin/dashboard/1` and `/admin/dashboard/2` to see populated charts.

## User Flow

1. **Create a campaign** — `/admin/campaigns/new` → fill the form → submit.
   Bad input (real brand, external landing URL) is rejected with an error.
2. **Preview** (no logging) — `/message/<id>/preview`.
3. **View as a subject** (logs `message_opened`) —
   `/message/<id>/view?subject=subject-01`.
4. **Click the call-to-action** — routes to the fake login page
   `/landing/<id>?subject=subject-01&variant=A` and logs `link_clicked` +
   `landing_visited`.
5. **Type anything and submit** — the browser sends only `{subject_code,
   variant, field_count}`; the server logs `fake_submit_attempted` with
   `{"field_count": N}` and nothing else.
6. **Debrief** — `/landing/debrief` explains what happened. `tracker.js`
   posts `form_interaction_started` (on first focus) and `landing_exited`
   (with `time_on_page_ms`) along the way.
7. **Dashboard** — `/admin/dashboard/<id>` shows the funnel, the A-vs-B
   comparison, and average-time tiles. Data comes from
   `/admin/dashboard/<id>/data` as JSON `{campaign, totals, variants}`.

## Recipients & test email

Each campaign has its own recipient list (approved internal test addresses).
On the campaign detail page:

- **Recipients section** — paste one email per line (commas also split).
  Whitespace is trimmed, blank lines ignored, duplicates collapsed
  case-insensitively, each address validated, capped at `MAX_RECIPIENTS`.
- **"Send test email" button** — sends the simulated message to every
  recipient and shows an inline summary (`Sent to N recipient(s)`, with a
  per-recipient error list if any failed).

The email contains the campaign's subject + body and a link back to the
local message view; clicks are tracked via a **derived pseudonymous code
per recipient** (e.g. `r3-1a2b3c4d`), so real email addresses never enter
the `events` table.

### Mail mode (sandbox by default)

```
# Sandbox (default): records to a local `outbox` table, NEVER touches the network.
python run.py

# Real SMTP (opt-in, authorized internal training only).
# Example with a local MailHog catch-all:
$env:MAIL_MODE = "smtp"
$env:MAIL_SMTP_HOST = "127.0.0.1"
$env:MAIL_SMTP_PORT = "1025"
$env:MAIL_FROM = "phishing-sim@internal.lab"
$env:MAIL_ALLOWED_DOMAINS = "internal.lab"   # strongly recommended
python run.py
```

Env knobs: `MAIL_MODE` (`sandbox`|`smtp`), `MAIL_FROM`, `MAIL_SMTP_HOST`,
`MAIL_SMTP_PORT`, `MAIL_SMTP_USER`, `MAIL_SMTP_PASSWORD` (secret — env
only), `MAIL_SMTP_USE_TLS`, `MAIL_ALLOWED_DOMAINS` (comma-separated),
`APP_BASE_URL` (link target).

**Guardrails kept under both modes:** the real `From` is always
`MAIL_FROM` (no sender spoofing); the landing page captures only a field
count (no credential capture); the outbox is the audit trail; recipient
addresses never enter the funnel's `events` table.

## Test It

```
pytest                        # full suite
pytest -k safety              # just the ethics/safety assertions
pytest tests/unit             # unit tests (validators, dashboard service, safety)
pytest tests/integration      # route + flow + seed + credential-leak tests
```

The tests run against a fresh temporary SQLite database, so they never touch
`data/phishing_sim.sqlite`.

### End-to-end browser test (optional)

A Playwright test (`tests/e2e/`) drives a real Chromium browser through the
whole funnel — author a campaign, view as a subject, click, submit the fake
login, reach the debrief, read the dashboard — and asserts the dashboard shows
the funnel numbers while nothing typed into the form is ever stored. Its
dependencies are kept out of the core install:

```
pip install -r requirements-e2e.txt
playwright install chromium
pytest tests/e2e
```

If Playwright is not installed, the e2e module is skipped, so a plain `pytest`
stays green and dependency-light.

## Project Layout

```
network_security/
├── app/                Backend (Flask blueprints + services + models)
│   ├── campaign/       Create / list / read campaigns; DEMO_MODE seeder
│   ├── message/        Render the simulated message; pick A/B variant
│   ├── landing/        Fake login page, safe submit, debrief
│   ├── logging_mod/    record_event — the ONLY writer of the events table
│   ├── dashboard/      Aggregate events into funnel + A/B numbers
│   ├── mail/           Sandbox-default mail sender + SMTP opt-in
│   ├── db.py           Connection lifecycle + schema bootstrap
│   ├── models.py       The ONLY module that contains SQL
│   ├── validators.py   Ethics guards
│   └── constants.py    Canonical event / variant / template strings
├── templates/          Jinja2 templates (admin, message, landing)
├── static/             css/styles.css, js/tracker.js, js/charts.js
├── data/               SQLite file (created at runtime, gitignored)
├── tests/              pytest unit + integration tests
├── docs/               report.md + screenshots/
├── run.py              Entry point (binds to 127.0.0.1)
├── config.py           Configuration + the ethics blocklists
└── requirements.txt
```

## Documentation

- **`docs/report.md`** — consolidated submission report: architecture, build
  narrative, ethics reasoning, and the metrics the dashboard produces.
- **`IMPLEMENTATION_PLAN.md`** — the full code-level plan (folder layout,
  function signatures, schema, routes, commit plan, tests).
- **`PLANNING.md`** — the high-level report-style planning document (what and
  why, schedule, ethics, future work).
- **`docs/screenshots/`** — per-step screenshots of the user flow (see
  `docs/screenshots/CAPTURE_LIST.md`).
