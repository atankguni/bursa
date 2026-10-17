"""
mail/registry.py
----------------
Resolves `settings.mail_provider` into a configured adapter, or None when email
is disabled, the name is unknown, or the provider's settings are missing.
"""

import logging

from config import settings
from mail.base import MailProvider
from mail.console import ConsoleProvider
from mail.resend import ResendProvider
from mail.smtp import SmtpProvider

log = logging.getLogger("bursa.mail")

# name -> adapter class. Add new providers here.
_REGISTRY: dict[str, type[MailProvider]] = {
    SmtpProvider.name: SmtpProvider,
    ResendProvider.name: ResendProvider,
    ConsoleProvider.name: ConsoleProvider,  # development: prints to the log
}


def provider_name() -> str | None:
    name = (settings.mail_provider or "").strip().lower()
    return name or None


def get_provider() -> MailProvider | None:
    name = provider_name()
    if name is None:
        return None
    cls = _REGISTRY.get(name)
    if cls is None:
        log.warning("Unknown mail provider %r (known: %s)", name, sorted(_REGISTRY))
        return None
    try:
        return cls.from_settings(settings)
    except ValueError as exc:  # e.g. an invalid smtp_security value
        log.warning("Mail provider %r is misconfigured: %s", name, exc)
        return None


def setup_hint() -> str:
    """What to set to enable email with the chosen (or any) provider."""
    cls = _REGISTRY.get(provider_name() or "")
    if cls is None:
        return f"MAIL_PROVIDER ({' or '.join(sorted(_REGISTRY))})"
    if cls is ConsoleProvider:
        return "PUBLIC_URL on localhost (the console provider is for development only)"
    return ", ".join((*cls.required_env, "MAIL_TO"))
