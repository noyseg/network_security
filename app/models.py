"""Data-access layer.

This module is the ONLY place in the project that contains SQL. Each function
does one job, takes plain Python values, returns plain Python values, and
raises ``sqlite3.Error`` for database problems. No function here validates
business rules — that is the services' responsibility.
"""

import json
from datetime import datetime
from typing import Optional

from app.db import get_connection


# --- Campaigns --------------------------------------------------------------


def insert_campaign(payload: dict) -> int:
    """Insert a row into ``campaigns`` and return its ID."""
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO campaigns
            (title, sender_name, subject, body_a, body_b,
             cta_text, landing_path, template_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["title"],
            payload["sender_name"],
            payload["subject"],
            payload["body_a"],
            payload.get("body_b"),
            payload["cta_text"],
            payload["landing_path"],
            payload["template_type"],
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_campaign_by_id(campaign_id: int) -> Optional[dict]:
    """Fetch one campaign by ID; return a plain dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?",
        (int(campaign_id),),
    ).fetchone()
    return dict(row) if row else None


def list_campaigns() -> list[dict]:
    """Return all campaigns, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM campaigns ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# --- Subjects ---------------------------------------------------------------


def get_or_create_subject(subject_code: str, note: Optional[str] = None) -> int:
    """Look up a subject by code; insert if missing; return its integer ID.

    Uses INSERT OR IGNORE to stay safe under concurrent inserts.
    """
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO subjects (subject_code, note) VALUES (?, ?)",
            (subject_code, note),
        )
    row = conn.execute(
        "SELECT id FROM subjects WHERE subject_code = ?",
        (subject_code,),
    ).fetchone()
    return int(row["id"])


# --- Events -----------------------------------------------------------------


def insert_event(
    campaign_id: int,
    subject_id: int,
    variant: str,
    event_type: str,
    metadata_json: Optional[str] = None,
) -> int:
    """Insert one row into ``events`` and return its ID.

    May raise sqlite3.IntegrityError when the partial UNIQUE index on
    dedup-once event types fires. Callers in the Logging service catch
    this and call ``find_event`` to return the surviving row.
    """
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO events (campaign_id, subject_id, variant, event_type, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (int(campaign_id), int(subject_id), variant, event_type, metadata_json),
    )
    conn.commit()
    return int(cur.lastrowid)


def find_event(
    campaign_id: int, subject_id: int, event_type: str
) -> Optional[dict]:
    """Find the first existing event row matching the triple, if any."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT * FROM events
        WHERE campaign_id = ? AND subject_id = ? AND event_type = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (int(campaign_id), int(subject_id), event_type),
    ).fetchone()
    return dict(row) if row else None


def update_event_metadata(
    event_id: int,
    metadata_json: Optional[str],
    created_at: Optional[datetime] = None,
) -> None:
    """Update an event's metadata (and optionally its timestamp).

    Used by the Logging service to keep only the latest ``landing_exited``
    row per (campaign, subject).
    """
    conn = get_connection()
    if created_at is None:
        conn.execute(
            "UPDATE events SET metadata_json = ? WHERE id = ?",
            (metadata_json, int(event_id)),
        )
    else:
        conn.execute(
            "UPDATE events SET metadata_json = ?, created_at = ? WHERE id = ?",
            (metadata_json, created_at, int(event_id)),
        )
    conn.commit()


def count_distinct_subjects_by_event(
    campaign_id: int,
    event_type: str,
    variant: Optional[str] = None,
) -> int:
    """Count distinct subjects who have at least one row of this event type."""
    conn = get_connection()
    if variant is None:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT subject_id) AS n
            FROM events
            WHERE campaign_id = ? AND event_type = ?
            """,
            (int(campaign_id), event_type),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT subject_id) AS n
            FROM events
            WHERE campaign_id = ? AND event_type = ? AND variant = ?
            """,
            (int(campaign_id), event_type, variant),
        ).fetchone()
    return int(row["n"] or 0)


def get_first_event_time(
    campaign_id: int, subject_id: int, event_type: str
) -> Optional[datetime]:
    """Earliest ``created_at`` for the triple, or None."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT MIN(created_at) AS t FROM events
        WHERE campaign_id = ? AND subject_id = ? AND event_type = ?
        """,
        (int(campaign_id), int(subject_id), event_type),
    ).fetchone()
    return row["t"] if row and row["t"] else None


def get_latest_event_time(
    campaign_id: int, subject_id: int, event_type: str
) -> Optional[datetime]:
    """Latest ``created_at`` for the triple, or None."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT MAX(created_at) AS t FROM events
        WHERE campaign_id = ? AND subject_id = ? AND event_type = ?
        """,
        (int(campaign_id), int(subject_id), event_type),
    ).fetchone()
    return row["t"] if row and row["t"] else None


def get_event_metadata(event_id: int) -> Optional[dict]:
    """Read and parse the ``metadata_json`` of one event."""
    conn = get_connection()
    row = conn.execute(
        "SELECT metadata_json FROM events WHERE id = ?",
        (int(event_id),),
    ).fetchone()
    if not row or not row["metadata_json"]:
        return None
    try:
        return json.loads(row["metadata_json"])
    except json.JSONDecodeError:
        return None


def list_subjects_with_event(
    campaign_id: int,
    event_type: str,
    variant: Optional[str] = None,
) -> list[int]:
    """Return all subject IDs who have at least one row of this event type."""
    conn = get_connection()
    if variant is None:
        rows = conn.execute(
            """
            SELECT DISTINCT subject_id FROM events
            WHERE campaign_id = ? AND event_type = ?
            """,
            (int(campaign_id), event_type),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT DISTINCT subject_id FROM events
            WHERE campaign_id = ? AND event_type = ? AND variant = ?
            """,
            (int(campaign_id), event_type, variant),
        ).fetchall()
    return [int(r["subject_id"]) for r in rows]
