"""
alerts/notify.py
----------------
Out-of-app notifications for triggered alerts. Telegram today (free, common in
Indonesia); each channel is optional and configured via backend/.env.

Delivery is best-effort: a failed send is logged and never blocks alert
evaluation (the in-app notification is always recorded first).
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request

from config import settings

log = logging.getLogger("bursa.notify")

_TELEGRAM = "https://api.telegram.org/bot{token}/sendMessage"


class NotifyError(RuntimeError):
    pass


def telegram_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _send_telegram(text: str) -> None:
    req = urllib.request.Request(
        _TELEGRAM.format(token=settings.telegram_bot_token),
        data=json.dumps({
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        # Telegram explains the problem (bad token, unknown chat) in the body.
        try:
            detail = json.loads(exc.read() or b"{}").get("description", "")
        except ValueError:
            detail = ""
        raise NotifyError(f"Telegram HTTP {exc.code}: {detail}".strip()) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise NotifyError(f"Telegram unreachable: {exc}") from exc
    if not body.get("ok"):
        raise NotifyError(f"Telegram refused: {body.get('description', 'unknown error')}")


async def send(text: str) -> None:
    """Send to every configured channel. Raises NotifyError if one fails."""
    if telegram_configured():
        await asyncio.to_thread(_send_telegram, text)


async def send_quietly(text: str) -> bool:
    """Best-effort send for background use; returns whether it was delivered."""
    if not telegram_configured():
        return False
    try:
        await send(text)
        return True
    except NotifyError as exc:
        log.warning("Notification not delivered: %s", exc)
        return False
