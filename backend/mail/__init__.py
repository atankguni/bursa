"""
Email: a provider-neutral mail service (SMTP or Resend today).

Everything outside this package uses only these names; see mail/base.py for
adding a provider and docs/configuration.md for setup.
"""

from mail.base import Attachment, Email, MailBusyError, MailError
from mail.service import MailNotConfiguredError, configured, send, send_quietly, status

__all__ = [
    "Attachment",
    "Email",
    "MailBusyError",
    "MailError",
    "MailNotConfiguredError",
    "configured",
    "send",
    "send_quietly",
    "status",
]
