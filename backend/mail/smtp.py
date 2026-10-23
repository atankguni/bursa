"""
mail/smtp.py
------------
SMTP adapter (standard library only). Works with any mailbox that allows SMTP:
Gmail / Google Workspace (an app password), Outlook, Zoho, or a transactional
relay such as Brevo or Mailgun.

  MAIL_PROVIDER=smtp
  SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_SECURITY=starttls
  SMTP_USERNAME=you@gmail.com  SMTP_PASSWORD=<app password>
  MAIL_FROM="Bursa <you@gmail.com>"  MAIL_TO=you@gmail.com
"""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import TYPE_CHECKING, Self

from mail.base import Email, MailBusyError, MailError, MailProvider

if TYPE_CHECKING:
    from config import Settings

_SECURITY = ("starttls", "ssl", "none")


def build_mime(email: Email, sender: str) -> EmailMessage:
    """Plain text, with an HTML alternative and attachments when present."""
    msg = EmailMessage()
    msg["Subject"] = email.subject
    msg["From"] = sender
    msg["To"] = ", ".join(email.to)
    if email.reply_to:
        msg["Reply-To"] = email.reply_to
    msg["Date"] = formatdate(localtime=True)
    domain = parseaddr(sender)[1].rpartition("@")[2] or None
    msg["Message-ID"] = make_msgid(domain=domain)
    msg.set_content(email.text)
    if email.html:
        msg.add_alternative(email.html, subtype="html")
    for a in email.attachments:
        maintype, _, subtype = a.mime_type.partition("/")
        msg.add_attachment(
            a.content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=a.filename,
        )
    return msg


class SmtpProvider(MailProvider):
    name = "smtp"
    required_env = ("SMTP_HOST", "MAIL_FROM")

    def __init__(
        self,
        *,
        host: str,
        port: int,
        security: str,
        username: str | None,
        password: str | None,
        timeout: float,
    ) -> None:
        if security not in _SECURITY:
            raise ValueError(f"smtp_security must be one of {_SECURITY}, not {security!r}")
        self.host = host
        self.port = port
        self.security = security
        self.username = username
        self.password = password
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Settings) -> Self | None:
        if not settings.smtp_host:
            return None
        return cls(
            host=settings.smtp_host,
            port=settings.smtp_port,
            security=settings.smtp_security.lower(),
            username=settings.smtp_username,
            password=settings.smtp_password,
            timeout=settings.mail_timeout_seconds,
        )

    async def send(self, email: Email) -> str | None:
        assert email.sender is not None  # filled in by mail.service
        msg = build_mime(email, email.sender)
        await asyncio.to_thread(self._deliver, msg)
        return msg["Message-ID"]

    def _deliver(self, msg: EmailMessage) -> None:
        context = ssl.create_default_context()
        try:
            if self.security == "ssl":
                server: smtplib.SMTP = smtplib.SMTP_SSL(
                    self.host, self.port, timeout=self.timeout, context=context
                )
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            with server:
                if self.security == "starttls":
                    server.starttls(context=context)
                if self.username:
                    server.login(self.username, self.password or "")
                server.send_message(msg)
        except smtplib.SMTPAuthenticationError as exc:
            raise MailError(
                "SMTP login failed: check SMTP_USERNAME / SMTP_PASSWORD "
                "(Gmail and Outlook need an app password)"
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise MailError(f"Recipient refused: {', '.join(exc.recipients)}") from exc
        except smtplib.SMTPSenderRefused as exc:
            raise MailError(f"Sender refused ({exc.smtp_code}): check MAIL_FROM") from exc
        except smtplib.SMTPResponseException as exc:
            # 4xx = temporary (greylisting, rate limit); 5xx = permanent.
            detail = exc.smtp_error.decode(errors="replace") if isinstance(
                exc.smtp_error, bytes) else str(exc.smtp_error)
            error = MailBusyError if 400 <= exc.smtp_code < 500 else MailError
            raise error(f"SMTP {exc.smtp_code}: {detail}") from exc
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as exc:
            raise MailBusyError(f"SMTP server unavailable: {exc}") from exc
        except smtplib.SMTPNotSupportedError as exc:
            raise MailError(f"SMTP server doesn't support this: {exc} "
                            "(check SMTP_SECURITY / SMTP_PORT)") from exc
        except ssl.SSLError as exc:
            raise MailError(f"TLS failed: {exc} (check SMTP_SECURITY / SMTP_PORT)") from exc
        except OSError as exc:  # DNS, refused connection, timeout
            raise MailBusyError(f"Can't reach {self.host}:{self.port}: {exc}") from exc
