"""SQLite connection helpers and schema bootstrap.

This is the ONLY module in the application that opens raw SQLite connections.
All SQL execution itself lives in ``app/models.py``; this file provides the
plumbing (connection lifecycle, schema creation, foreign-key pragma).
"""

import sqlite3
from typing import Optional

from flask import current_app, g

from config import Config


# --- Schema -----------------------------------------------------------------

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS campaigns (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        title         TEXT NOT NULL,
        sender_name   TEXT NOT NULL,
        subject       TEXT NOT NULL,
        body_a        TEXT NOT NULL,
        body_b        TEXT,
        cta_text      TEXT NOT NULL,
        landing_path  TEXT NOT NULL,
        template_type TEXT NOT NULL CHECK (template_type IN ('single','ab')),
        created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subjects (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_code TEXT NOT NULL UNIQUE,
        note         TEXT,
        created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id   INTEGER NOT NULL REFERENCES campaigns(id),
        subject_id    INTEGER NOT NULL REFERENCES subjects(id),
        variant       TEXT NOT NULL CHECK (variant IN ('A','B')),
        event_type    TEXT NOT NULL,
        metadata_json TEXT,
        created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Non-unique index for fast dashboard / find_event lookups.
    """
    CREATE INDEX IF NOT EXISTS idx_events_lookup
        ON events (campaign_id, subject_id, event_type)
    """,
    # Partial UNIQUE index — the database-level guarantee that the four
    # dedup-once event types appear at most once per (campaign, subject).
    # See IMPLEMENTATION_PLAN.md section 8.4.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_events_dedup_once
        ON events (campaign_id, subject_id, event_type)
        WHERE event_type IN (
            'message_opened',
            'link_clicked',
            'landing_visited',
            'form_interaction_started'
        )
    """,
)


# --- Connection lifecycle ---------------------------------------------------


def _db_path() -> str:
    """Return the configured SQLite path, working with or without app context."""
    try:
        return current_app.config["DB_PATH"]
    except RuntimeError:
        return Config.DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a per-request SQLite connection.

    Inside a Flask request context the connection is cached on ``g`` so all
    code within a single request shares one connection and one transaction
    scope. Outside a request (e.g. tests, scripts), a fresh connection is
    opened and the caller is responsible for closing it.
    """
    try:
        # Inside a request context.
        if "db_conn" not in g:
            g.db_conn = _open_connection()
        return g.db_conn
    except RuntimeError:
        # Outside a request context.
        return _open_connection()


def _open_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_connection(_exc: Optional[BaseException] = None) -> None:
    """Teardown handler: close the per-request connection if present."""
    try:
        conn = g.pop("db_conn", None)
    except RuntimeError:
        conn = None
    if conn is not None:
        conn.close()


# --- Schema bootstrap -------------------------------------------------------


def init_schema() -> None:
    """Create all tables and indexes if they do not exist.

    Safe to call repeatedly. Used by the app factory at startup and by the
    pytest fixtures before each test session.
    """
    conn = _open_connection()
    try:
        with conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
    finally:
        conn.close()
