"""Ethics guards.

Every safety rule that defines this project is enforced by a function in
this file. Other modules call these guards before doing anything that
touches the database or renders user-visible content.
"""

from typing import Any
from urllib.parse import urlparse

from config import Config


# --- Sender / template body --------------------------------------------------


def is_sender_fictional(sender_name: str) -> bool:
    """Return True iff ``sender_name`` contains no known real-brand token."""
    if not isinstance(sender_name, str):
        raise TypeError("sender_name must be a string")
    if not sender_name.strip():
        return False
    lowered = sender_name.lower()
    for token in Config.DISALLOWED_BRANDS:
        if token in lowered:
            return False
    return True


def is_template_safe(body_text: str) -> bool:
    """Return True iff ``body_text`` contains no known real-brand token."""
    if not isinstance(body_text, str):
        raise TypeError("body_text must be a string")
    lowered = body_text.lower()
    for token in Config.DISALLOWED_BRANDS:
        if token in lowered:
            return False
    return True


# --- Landing path -----------------------------------------------------------


def is_landing_link_local(url: str) -> bool:
    """Accept only paths served by this app on localhost.

    Accepts:
      * relative path starting with ``/landing/``
      * absolute URL whose host is 127.0.0.1 or localhost AND whose path
        starts with ``/landing/``.
    """
    if not isinstance(url, str):
        raise TypeError("url must be a string")
    if not url:
        return False

    if url.startswith("/landing/"):
        return True

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host in ("127.0.0.1", "localhost") and path.startswith("/landing/"):
        return True
    return False


# --- Sensitive payload guard ------------------------------------------------


def assert_no_credential_payload(payload: Any) -> None:
    """Raise ``ValueError`` if ``payload`` contains any sensitive key.

    Recurses into nested dicts and into dicts inside lists. ``None`` is a
    no-op. A non-dict at the top level raises ``TypeError`` — the function
    is intended for structured event metadata.
    """
    if payload is None:
        return
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict or None")

    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"non-string key in payload: {key!r}")
        lowered = key.lower()
        for token in Config.SENSITIVE_KEYS:
            if token in lowered:
                raise ValueError(
                    f"sensitive key '{key}' is not allowed in event metadata"
                )
        # Recurse into nested structures.
        if isinstance(value, dict):
            assert_no_credential_payload(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    assert_no_credential_payload(item)


# --- Event-type allow-list --------------------------------------------------


def is_allowed_event_type(event_type: str) -> bool:
    """Return True iff ``event_type`` is in the closed allow-list."""
    if not isinstance(event_type, str):
        raise TypeError("event_type must be a string")
    return event_type in Config.ALLOWED_EVENT_TYPES


# --- Subject code ----------------------------------------------------------


def is_valid_subject_code(subject_code: str) -> bool:
    """Subject codes are pseudonymous internal labels.

    Allowed shape: starts with a letter, then letters/digits/dashes only,
    1..MAX_SUBJECT_CODE_LENGTH chars long.
    """
    if not isinstance(subject_code, str):
        return False
    if not subject_code:
        return False
    if len(subject_code) > Config.MAX_SUBJECT_CODE_LENGTH:
        return False
    if not subject_code[0].isalpha():
        return False
    for ch in subject_code[1:]:
        if not (ch.isalnum() or ch in "-_"):
            return False
    return True
