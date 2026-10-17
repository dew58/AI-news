"""Deliver an HTML digest through Gmail's authenticated SSL SMTP endpoint."""

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when delivery configuration or the SMTP transaction fails."""


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise EmailDeliveryError(f"Missing required setting {name}; add it to your .env file.")
    return value


def _validate_address(name: str, value: str) -> str:
    _, address = parseaddr(value)
    if address != value or "@" not in address or address.startswith("@") or address.endswith("@"):
        raise EmailDeliveryError(f"{name} must be a valid email address.")
    return address


def send_digest(html: str, subject: str | None = None) -> None:
    """Send HTML email using Gmail App Password credentials from the environment."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("html must be a non-empty string")

    sender = _validate_address("GMAIL_ADDRESS", _required_setting("GMAIL_ADDRESS"))
    password = _required_setting("GMAIL_APP_PASSWORD").replace(" ", "")
    recipient = _validate_address("RECIPIENT_EMAIL", _required_setting("RECIPIENT_EMAIL"))

    message = EmailMessage()
    message["Subject"] = subject or f"AI & Tech Daily Digest — {datetime.now(timezone.utc):%B %d, %Y}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content("This digest is available in HTML format.")
    message.add_alternative(html, subtype="html", charset="utf-8")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Gmail SMTP delivery failed")
        raise EmailDeliveryError("Gmail delivery failed. Check Gmail settings and app-password access.") from exc

    logger.info("Digest email sent to %s", recipient)


__all__ = ["EmailDeliveryError", "send_digest"]
