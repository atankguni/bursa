"""
mail/service.py
---------------
The one entry point for sending email. Fills in the configured sender and
default recipients, validates the message, and hands it to the active provider.

    from mail import Email, send

    await send(Email(subject="Daily digest", text=body_text, html=body_html))

Use `send` when the caller should see the error (e.g. a "send test" button), and
`send_quietly` for background jobs, where a failed email is logged and must
never break the job.
"""

import logging
from dataclasses import replace

from config import settings
from mail.base import Email, MailError, split_addresses, validate
from mail.registry import get_provider, provider_name, setup_hint

log = logging.getLogger("bursa.mail")


class MailNotConfiguredError(MailError):
    """Email is disabled or its provider settings are incomplete."""


def configured() -> bool:
    """A provider is set up and there is a sender. (Recipients may come per call.)"""
    return get_provider() is not None and bool(settings.mail_from)


def default_recipients() -> tuple[str, ...]:
    return split_addresses(settings.mail_to)


async def send(email: Email) -> str | None:
    """
    Send one message; returns the provider's message id when it gives one.
    Raises MailNotConfiguredError, MailBusyError (retry later) or MailError.
    """
    provider = get_provider()
    if provider is None or not settings.mail_from:
        raise MailNotConfiguredError(f"Email isn't set up: set {setup_hint()} in backend/.env")
    email = replace(
        email,
        sender=email.sender or settings.mail_from,
        to=email.to or default_recipients(),
    )
    validate(email)
    message_id = await provider.send(email)
    # Log the subject and count only: addresses and content stay out of the logs.
    log.info("Email sent via %s: %r to %d recipient(s)", provider.name, email.subject,
             len(email.to))
    return message_id


async def send_quietly(email: Email) -> bool:
    """Best-effort send for background use; returns whether it was delivered."""
    if not configured():
        return False
    try:
        await send(email)
        return True
    except MailError as exc:
        log.warning("Email %r not delivered: %s", email.subject, exc)
        return False


def status() -> dict[str, object]:
    return {
        "configured": configured(),
        "provider": provider_name(),
        "sender": settings.mail_from if configured() else None,
        "recipients": len(default_recipients()),
        "setup_hint": "" if configured() and default_recipients() else setup_hint(),
    }
