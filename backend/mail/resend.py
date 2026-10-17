"""
mail/resend.py
--------------
Resend API adapter (https://resend.com; free tier: 3,000 emails/month).
Real delivery needs a domain verified in Resend; until then Resend only sends
from its test sender to the account owner's own address.

  MAIL_PROVIDER=resend
  RESEND_API_KEY=re_...
  MAIL_FROM="Bursa <bursa@your-domain.com>"  MAIL_TO=you@example.com
"""

import asyncio
import base64
import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Self

from mail.base import Email, MailBusyError, MailError, MailProvider

if TYPE_CHECKING:
    from config import Settings

_ENDPOINT = "https://api.resend.com/emails"


class ResendProvider(MailProvider):
    name = "resend"
    required_env = ("RESEND_API_KEY", "MAIL_FROM")

    def __init__(self, *, api_key: str, timeout: float) -> None:
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: "Settings") -> Self | None:
        if not settings.resend_api_key:
            return None
        return cls(api_key=settings.resend_api_key, timeout=settings.mail_timeout_seconds)

    @staticmethod
    def payload(email: Email) -> dict[str, Any]:
        body: dict[str, Any] = {
            "from": email.sender,
            "to": list(email.to),
            "subject": email.subject,
            "text": email.text,
        }
        if email.html:
            body["html"] = email.html
        if email.reply_to:
            body["reply_to"] = email.reply_to
        if email.attachments:
            body["attachments"] = [
                {
                    "filename": a.filename,
                    "content": base64.b64encode(a.content).decode(),
                    "content_type": a.mime_type,
                }
                for a in email.attachments
            ]
        return body

    async def send(self, email: Email) -> str | None:
        return await asyncio.to_thread(self._post, self.payload(email))

    def _post(self, body: dict[str, Any]) -> str | None:
        req = urllib.request.Request(
            _ENDPOINT,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Resend's edge rejects urllib's default User-Agent.
                "User-Agent": "bursa-mail/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            # Resend explains the problem in the body: {"message": "...", "name": "..."}.
            try:
                detail = json.loads(exc.read() or b"{}").get("message", "")
            except ValueError:
                detail = ""
            error = MailBusyError if exc.code == 429 or exc.code >= 500 else MailError
            raise error(f"Resend HTTP {exc.code}: {detail}".strip()) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise MailBusyError(f"Resend unreachable: {exc}") from exc
        return data.get("id") if isinstance(data, dict) else None
