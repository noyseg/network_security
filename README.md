# Controlled Phishing Simulation Platform

A **local, lab-only** educational platform for studying the human factor in
network security. The system simulates a phishing campaign end-to-end —
message preview, fake landing page, safe event tracking, dashboard — without
ever sending real email, impersonating a real organization, or collecting real
credentials.

**Course:** Network Security — Mini-Project
**Authors:** Noy Segal, Noam Tamari

## Ethical Limits (Hard Rules)

1. **Local / lab use only.** The development server binds to `127.0.0.1`.
2. **No real organizations.** Sender names and template bodies are checked
   against a blocklist of real brands.
3. **No real users.** Test subjects are pseudonymous internal labels
   (e.g. `subject-01`) — never real email addresses.
4. **No real passwords.** The fake submit endpoint accepts only an integer
   field count; it cannot receive names or values.
5. **Safe logging only.** Events are limited to a closed allow-list and a
   credential-payload guard runs on every event write.

These rules are encoded in code (`app/validators.py`) and in tests
(`tests/unit/test_validators.py`, `tests/integration/test_no_credentials_stored.py`).

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

## Test It

```
pytest
```

## Project Layout

```
phishing-sim/
├── app/             Backend (Flask blueprints + services + models)
├── templates/       Jinja2 templates
├── static/          CSS, JS, images
├── data/            SQLite file (created at runtime, gitignored)
├── tests/           pytest unit + integration + scenario tests
├── run.py           Entry point (binds to 127.0.0.1)
├── config.py        Configuration
└── requirements.txt
```

For the full design, see `IMPLEMENTATION_PLAN.md`. For the high-level report,
see `PLANNING.md`.
