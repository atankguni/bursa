"""
mail/schemas.py
---------------
API models (Pydantic) for email.
"""

from schemas import Schema


class MailStatusOut(Schema):
    """Email delivery setup (no secrets: provider name and sender only)."""

    configured: bool
    provider: str | None
    sender: str | None
    recipients: int  # default recipients in MAIL_TO
    setup_hint: str = ""  # what to set when not (fully) configured


class MailTestOut(Schema):
    delivered: bool
    message_id: str | None = None
