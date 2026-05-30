"""Static configuration for the phishing-simulation platform.

This file is intentionally simple: a single Config class with class-level
attributes. No environment files, no factories. The values here are the
single source of truth for the application's safety constraints.
"""

import os


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Application configuration.

    All hard ethical constraints live here as data so they can be referenced
    from validators, services, and tests without duplication.
    """

    # --- Server binding (LOCAL ONLY) -------------------------------------
    HOST = "127.0.0.1"
    PORT = 5000
    DEBUG = True

    # --- Demo mode -------------------------------------------------------
    # When True, the app factory seeds two demo campaigns and a few
    # pseudonymous subjects so the demo is one command to start.
    DEMO_MODE = bool(int(os.environ.get("DEMO_MODE", "0")))

    # --- Database --------------------------------------------------------
    DB_PATH = os.path.join(BASE_DIR, "data", "phishing_sim.sqlite")

    # --- Ethics: brand blocklist ----------------------------------------
    # Substring tokens (lowercase). Any campaign sender_name or template
    # body containing one of these is rejected by validators. The list is
    # intentionally illustrative and easy to extend.
    DISALLOWED_BRANDS = (
        # Banks
        "bank", "chase", "wells fargo", "hsbc", "citibank", "barclays",
        "leumi", "hapoalim", "discount bank", "mizrahi",
        # Government / tax
        "irs", "tax authority", "social security", "medicare", "medicaid",
        "ministry of", "national insurance", "biton",
        # Payment networks
        "visa", "mastercard", "american express", "amex", "paypal",
        "stripe", "venmo", "zelle",
        # Big tech
        "google", "microsoft", "apple", "amazon", "facebook", "meta",
        "netflix", "linkedin", "twitter", "instagram", "tiktok",
        "dropbox", "github", "openai", "anthropic",
    )

    # --- Ethics: sensitive payload guard ---------------------------------
    # Substrings that, if found in a payload key (case-insensitive), cause
    # assert_no_credential_payload to raise ValueError.
    SENSITIVE_KEYS = (
        "password", "passwd", "pwd", "secret", "token",
        "pin", "card", "cvv", "ssn",
    )

    # --- Ethics: event allow-list ----------------------------------------
    ALLOWED_EVENT_TYPES = (
        "message_opened",
        "link_clicked",
        "landing_visited",
        "form_interaction_started",
        "fake_submit_attempted",
        "landing_exited",
    )

    # --- Variants --------------------------------------------------------
    ALLOWED_VARIANTS = ("A", "B")

    # --- Limits ---------------------------------------------------------
    MAX_TITLE_LENGTH = 200
    MAX_BODY_LENGTH = 10000
    MAX_SUBJECT_CODE_LENGTH = 40
    MAX_FIELD_COUNT = 20
    MAX_RECIPIENTS = 500

    # --- Mail (test-email sending) ---------------------------------------
    # SAFE BY DEFAULT: "sandbox" records each message to a local outbox and
    # never touches the network. "smtp" is an explicit opt-in for authorized
    # internal training only. The real From address is always MAIL_FROM (the
    # configured account) — the campaign sender_name is fictional display
    # text only; sender identity is never spoofed.
    MAIL_MODE = os.environ.get("MAIL_MODE", "sandbox")  # "sandbox" | "smtp"
    MAIL_FROM = os.environ.get("MAIL_FROM", "phishing-sim@localhost")
    MAIL_SMTP_HOST = os.environ.get("MAIL_SMTP_HOST", "")
    MAIL_SMTP_PORT = int(os.environ.get("MAIL_SMTP_PORT", "1025"))
    MAIL_SMTP_USER = os.environ.get("MAIL_SMTP_USER", "")
    # Secret: supplied via environment only, never hardcoded.
    MAIL_SMTP_PASSWORD = os.environ.get("MAIL_SMTP_PASSWORD", "")
    MAIL_SMTP_USE_TLS = bool(int(os.environ.get("MAIL_SMTP_USE_TLS", "0")))
    # Optional recipient-domain allowlist (comma-separated). Empty = no
    # restriction. Strongly recommended when MAIL_MODE=smtp.
    MAIL_ALLOWED_DOMAINS = tuple(
        d.strip().lower()
        for d in os.environ.get("MAIL_ALLOWED_DOMAINS", "").split(",")
        if d.strip()
    )
    # Base URL used to build links inside test emails. Local by default.
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")
