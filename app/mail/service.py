"""Mail service for sending simulated test emails.

SAFE BY DEFAULT. ``MAIL_MODE`` is ``"sandbox"`` unless explicitly set, and
the sandbox sender records each message to a local ``outbox`` table (and
the app log) WITHOUT touching the network. The ``smtp`` sender is an
explicit opt-in for authorized internal training; it uses only the Python
standard library, so no new dependency and no banned outbound-HTTP import.

Hard rules this module upholds:
* No sender spoofing — the real ``From`` is always ``Config.MAIL_FROM``;
  the campaign ``sender_name`` is fictional display text only.
* No credential capture — the email only links to the local simulation;
  the landing page still records nothing but a field count.
* Real recipient addresses never enter the ``events`` table — the link
  carries a pseudonymous, derived subject code instead.
* Every test email is clearly marked a simulation.
"""

import hashlib
from abc import ABC, abstractmethod

from flask import current_app

from app import models
from app.campaign import service as campaign_service
from config import Config


SIMULATION_FOOTER = (
    "\n\n---\n"
    "This message is part of an authorized security-awareness SIMULATION. "
    "It was not sent by the organization it may appear to reference, and no "
    "action is required. If you have questions, contact your security team."
)


class MailSender(ABC):
    """Provider-agnostic mail transport."""

    @abstractmethod
    def send(self, to_addr: str, subject: str, body: str) -> None:
        """Deliver one message, or raise on failure."""


class SandboxMailSender(MailSender):
    """Default sender: records to the local outbox; never hits the network."""

    def __init__(self, campaign_id: int):
        self._campaign_id = campaign_id

    def send(self, to_addr: str, subject: str, body: str) -> None:
        models.insert_outbox(
            self._campaign_id, to_addr, subject, body, mode="sandbox"
        )
        try:
            current_app.logger.info(
                "[sandbox-mail] would send to %s | subject=%r", to_addr, subject
            )
        except RuntimeError:
            pass  # outside an app context (e.g. a unit test) — outbox is enough


class SmtpMailSender(MailSender):
    """Real SMTP transport (opt-in). Stdlib only; From is never spoofed."""

    def __init__(self, campaign_id: int):
        self._campaign_id = campaign_id

    def send(self, to_addr: str, subject: str, body: str) -> None:
        # Imported lazily so the module never pulls smtplib in sandbox mode.
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = Config.MAIL_FROM  # the configured account, NOT spoofed
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(Config.MAIL_SMTP_HOST, Config.MAIL_SMTP_PORT) as smtp:
            if Config.MAIL_SMTP_USE_TLS:
                smtp.starttls()
            if Config.MAIL_SMTP_USER:
                smtp.login(Config.MAIL_SMTP_USER, Config.MAIL_SMTP_PASSWORD)
            smtp.send_message(msg)

        # Mirror real sends into the outbox too, for an auditable record.
        models.insert_outbox(
            self._campaign_id, to_addr, subject, body, mode="smtp"
        )


def get_mail_sender(campaign_id: int) -> MailSender:
    """Return the configured sender. Sandbox unless MAIL_MODE == 'smtp'."""
    if Config.MAIL_MODE == "smtp":
        return SmtpMailSender(campaign_id)
    return SandboxMailSender(campaign_id)


def _subject_code_for(campaign_id: int, email: str) -> str:
    """Derive a pseudonymous, funnel-safe subject code from an address.

    Keeps the real email out of the events table while still letting a
    recipient's click be attributed. Shape passes is_valid_subject_code.
    """
    digest = hashlib.sha256(f"{campaign_id}:{email.lower()}".encode()).hexdigest()
    return f"r{int(campaign_id)}-{digest[:8]}"


def build_email(campaign: dict, recipient: str) -> tuple[str, str]:
    """Build the (subject, body) for one recipient's simulated test email."""
    code = _subject_code_for(campaign["id"], recipient)
    link = (
        f"{Config.APP_BASE_URL}/message/{campaign['id']}/view"
        f"?subject={code}"
    )
    subject = f"[SIMULATION] {campaign['subject']}"
    body = (
        f"From (simulated): {campaign['sender_name']}\n\n"
        f"{campaign['body_a']}\n\n"
        f"{campaign['cta_text']}: {link}"
        f"{SIMULATION_FOOTER}"
    )
    return subject, body


def _domain_allowed(email: str) -> bool:
    if not Config.MAIL_ALLOWED_DOMAINS:
        return True
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in Config.MAIL_ALLOWED_DOMAINS


def send_test_email(campaign_id: int) -> dict:
    """Send the simulated message to every recipient of a campaign.

    Returns a summary dict: ``{total, sent, failed, errors}`` where
    ``errors`` is a list of ``{recipient, error}``.

    Raises ``ValueError`` for an unknown campaign or an empty recipient list.
    """
    campaign = campaign_service.get_campaign(campaign_id)
    if campaign is None:
        raise ValueError(f"campaign {campaign_id} does not exist")

    recipients = campaign_service.get_recipients(campaign_id)
    if not recipients:
        raise ValueError("campaign has no recipients")

    sender = get_mail_sender(campaign_id)
    sent = 0
    errors: list[dict] = []
    for addr in recipients:
        if not _domain_allowed(addr):
            errors.append(
                {"recipient": addr, "error": "domain not in MAIL_ALLOWED_DOMAINS"}
            )
            continue
        subject, body = build_email(campaign, addr)
        try:
            sender.send(addr, subject, body)
            sent += 1
        except Exception as exc:  # noqa: BLE001 — report any transport failure
            errors.append({"recipient": addr, "error": str(exc)})

    return {
        "total": len(recipients),
        "sent": sent,
        "failed": len(errors),
        "errors": errors,
    }
