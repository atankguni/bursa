"""
services/preferences.py
-----------------------
Server-side preferences, per user. Stored in the DB (not the browser) so
background work (rating-change alerts) uses the same investing style as the
user's pages.
"""

import logging
from datetime import UTC, datetime
from typing import cast, get_args

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.upsert import upsert
from models import RatingState, UserPreference
from schemas import DisplaySettings, InvestingStyle

INVESTING_STYLE_KEY = "investing_style"
ASSISTANT_PERSONAL_KEY = "assistant_personal_data"
DISPLAY_KEY = "display_settings"
ALERTS_SEEN_KEY = "alerts_seen_at"
DEFAULT_STYLE: InvestingStyle = "investor"
_STYLES: tuple[str, ...] = get_args(InvestingStyle)

log = logging.getLogger("bursa.preferences")


async def _get(session: AsyncSession, user_id: int, key: str) -> str | None:
    return (
        await session.execute(
            select(UserPreference.value).where(
                UserPreference.user_id == user_id, UserPreference.key == key
            )
        )
    ).scalar_one_or_none()


async def _set(session: AsyncSession, user_id: int, key: str, value: str) -> None:
    await upsert(
        session, UserPreference, {"user_id": user_id, "key": key, "value": value},
        keys=["user_id", "key"],
    )


async def get_investing_style(session: AsyncSession, user_id: int) -> InvestingStyle:
    value = await _get(session, user_id, INVESTING_STYLE_KEY)
    return cast(InvestingStyle, value) if value in _STYLES else DEFAULT_STYLE


async def styles_by_user(session: AsyncSession, user_ids: set[int]) -> dict[int, InvestingStyle]:
    """Investing style of several users at once (default for those who never chose)."""
    rows = (
        await session.execute(
            select(UserPreference.user_id, UserPreference.value).where(
                UserPreference.user_id.in_(user_ids), UserPreference.key == INVESTING_STYLE_KEY
            )
        )
    ).all()
    chosen = {uid: v for uid, v in rows if uid is not None and v in _STYLES}
    return {uid: cast(InvestingStyle, chosen.get(uid, DEFAULT_STYLE)) for uid in user_ids}


async def set_investing_style(session: AsyncSession, user_id: int, style: InvestingStyle) -> bool:
    """Persist the style. Returns True if it changed."""
    if style == await get_investing_style(session, user_id):
        return False
    await _set(session, user_id, INVESTING_STYLE_KEY, style)
    # Rating-change alerts compare against the last-seen rating. Ratings from the
    # other style aren't comparable, so drop this user's baselines (rebuilt on the
    # next evaluation) instead of firing a wave of "rating changed" alerts.
    await session.execute(delete(RatingState).where(RatingState.user_id == user_id))
    await session.commit()
    return True


async def get_assistant_personal_data(session: AsyncSession, user_id: int) -> bool:
    """Whether the AI assistant may read this user's watchlist/portfolio (opt-in).
    Falls back to the `assistant_personal_data` setting until the user chooses."""
    from config import settings

    value = await _get(session, user_id, ASSISTANT_PERSONAL_KEY)
    return settings.assistant_personal_data if value is None else value == "true"


async def set_assistant_personal_data(session: AsyncSession, user_id: int, enabled: bool) -> None:
    await _set(session, user_id, ASSISTANT_PERSONAL_KEY, "true" if enabled else "false")
    await session.commit()


async def get_display(session: AsyncSession, user_id: int) -> DisplaySettings | None:
    """Saved display settings, or None if never saved (or no longer valid)."""
    raw = await _get(session, user_id, DISPLAY_KEY)
    if raw is None:
        return None
    try:
        return DisplaySettings.model_validate_json(raw)
    except ValidationError:
        log.warning("Ignoring invalid display settings of user %d", user_id)
        return None


async def set_display(session: AsyncSession, user_id: int, display: DisplaySettings) -> None:
    await _set(session, user_id, DISPLAY_KEY, display.model_dump_json(by_alias=True))
    await session.commit()


async def get_alerts_seen_at(session: AsyncSession, user_id: int) -> datetime | None:
    raw = await _get(session, user_id, ALERTS_SEEN_KEY)
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


async def mark_alerts_seen(session: AsyncSession, user_id: int, up_to: datetime) -> None:
    """Alerts up to `up_to` were seen. Never moves back (another device may be behind)."""
    if up_to.tzinfo is not None:  # stored like AlertEvent.triggered_at: naive UTC
        up_to = up_to.astimezone(UTC).replace(tzinfo=None)
    current = await get_alerts_seen_at(session, user_id)
    if current is None or up_to > current:
        await _set(session, user_id, ALERTS_SEEN_KEY, up_to.isoformat())
        await session.commit()
