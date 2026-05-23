"""Canonical string constants used across modules.

Centralizing these prevents typos turning into silent data divergence
(``"message_opened"`` vs ``"message-opened"``). Other modules import from
here instead of hard-coding the values.
"""

# --- Event types (must mirror Config.ALLOWED_EVENT_TYPES) ---------------
EVENT_MESSAGE_OPENED = "message_opened"
EVENT_LINK_CLICKED = "link_clicked"
EVENT_LANDING_VISITED = "landing_visited"
EVENT_FORM_INTERACTION_STARTED = "form_interaction_started"
EVENT_FAKE_SUBMIT_ATTEMPTED = "fake_submit_attempted"
EVENT_LANDING_EXITED = "landing_exited"

# The subset of event types that should appear at most once per
# (campaign, subject). Enforced by the partial UNIQUE index on `events`
# and by the application-layer check inside record_event.
DEDUP_ONCE_EVENTS = (
    EVENT_MESSAGE_OPENED,
    EVENT_LINK_CLICKED,
    EVENT_LANDING_VISITED,
    EVENT_FORM_INTERACTION_STARTED,
)

# --- Variants ----------------------------------------------------------
VARIANT_A = "A"
VARIANT_B = "B"

# --- Template types ----------------------------------------------------
TEMPLATE_SINGLE = "single"
TEMPLATE_AB = "ab"
