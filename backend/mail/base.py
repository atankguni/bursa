"""
mail/base.py
------------
The provider-neutral contract every email adapter implements.

Callers build an `Email` and hand it to `mail.service.send`; they never see
SMTP or a vendor API. Adding a provider:
  1. subclass `MailProvider` in a new module (e.g. `mailgun.py`);
  2. register it in `registry.py`;
  3. add its settings to `config.Settings` (secrets in `backend/.env`);
  4. set `MAIL_PROVIDER=<name>`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.utils import getaddresses, parseaddr
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    from config import Settings


# --------------------------------------------------------------------------- #
# Errors (callers decide whether to retry; adapters only classify)
# --------------------------------------------------------------------------- #
class MailError(RuntimeError):
    """The message was refused: bad credentials, sender or recipient, or a bad
    request. Retrying the same message won't help."""


class MailBusyError(MailError):
    """Rate-limited, temporarily failing or unreachable: a later retry may work."""


# --------------------------------------------------------------------------- #
# Message
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


@dataclass(frozen=True)
class Email:
    """
    One message. `text` is required (every client can show it); `html` is an
    optional richer alternative. `to` and `sender` may be left empty to use the
    configured defaults (`mail_to`, `mail_from`).
    """

    subject: str
    text: str
    html: str | None = None
    to: tuple[str, ...] = ()
    sender: str | None = None
    reply_to: str | None = None
    attachments: tuple[Attachment, ...] = field(default=())


def _has_line_break(value: str) -> bool:
    return "\r" in value or "\n" in value


def is_valid_address(value: str) -> bool:
    """A single address, optionally with a display name ("Name <a@b.c>")."""
    if not value or _has_line_break(value):
        return False
    _, addr = parseaddr(value)
    local, at, domain = addr.rpartition("@")
    return bool(at and local and "." in domain and " " not in addr)


def split_addresses(value: str | None) -> tuple[str, ...]:
    """Comma-separated setting -> individual addresses (display names kept)."""
    if not value:
        return ()
    return tuple(
        f"{name} <{addr}>" if name else addr
        for name, addr in getaddresses([value])
        if addr
    )


def validate(email: Email) -> None:
    """Reject messages no provider should send. Header values must not contain
    line breaks (header injection), and every address must parse."""
    if not email.subject.strip() or _has_line_break(email.subject):
        raise MailError("Subject must be a single non-empty line")
    if not email.text.strip():
        raise MailError("A plain-text body is required")
    if not email.to:
        raise MailError("No recipients")
    for addr in (*email.to, email.sender or "", *([email.reply_to] if email.reply_to else [])):
        if not is_valid_address(addr):
            raise MailError(f"Invalid email address: {addr!r}")
    for a in email.attachments:
        if not a.filename or _has_line_break(a.filename) or "/" in a.filename:
            raise MailError(f"Invalid attachment filename: {a.filename!r}")


# --------------------------------------------------------------------------- #
# Adapter interface
# --------------------------------------------------------------------------- #
class MailProvider(ABC):
    name: ClassVar[str]
    # Settings / environment variables the provider needs (shown in setup hints).
    required_env: ClassVar[tuple[str, ...]]

    @classmethod
    @abstractmethod
    def from_settings(cls, settings: "Settings") -> Self | None:
        """Build from app settings, or None when its required settings are missing."""

    @abstractmethod
    async def send(self, email: Email) -> str | None:
        """Deliver one validated message (sender and recipients already filled in).

        Returns the provider's message id when it gives one. Raises MailBusyError
        or MailError; never logs or echoes credentials.
        """
