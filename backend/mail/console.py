"""
mail/console.py
---------------
Development only: print each email to the log instead of sending it, so
invites, password resets and 2FA codes can be read with `docker compose logs`.

  MAIL_PROVIDER=console      (MAIL_FROM optional)

Anyone who can read the logs can then use those codes and links, so it only
works while PUBLIC_URL points at this machine (localhost); anywhere else it
stays disabled and says why.
"""

import logging
import secrets
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit

from mail.base import Email, MailProvider

if TYPE_CHECKING:
    from config import Settings

log = logging.getLogger("bursa.mail.console")

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_local(public_url: str) -> bool:
    host = (urlsplit(public_url).hostname or "").lower()
    return host in _LOCAL_HOSTS or host.endswith(".localhost")


class ConsoleProvider(MailProvider):
    name = "console"
    required_env = ()
    default_sender = "Bursa (dev) <bursa@localhost.localdomain>"

    @classmethod
    def from_settings(cls, settings: "Settings") -> Self | None:
        if not is_local(settings.public_url):
            raise ValueError(
                "the console provider prints codes and links to the log, so it only "
                f"works when PUBLIC_URL is localhost (it is {settings.public_url})"
            )
        return cls()

    async def send(self, email: Email) -> str | None:
        rule = "=" * 72
        log.warning(
            "\n%s\nDEV EMAIL (not sent: MAIL_PROVIDER=console)\nTo: %s\nSubject: %s\n\n%s\n%s",
            rule, ", ".join(email.to), email.subject, email.text.strip(), rule,
        )
        return f"console-{secrets.token_hex(6)}"
