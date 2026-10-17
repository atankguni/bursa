"""
services/preferences.py
-----------------------
Server-side user preferences. Stored in the DB (not the browser) so background
work — rating-change alerts — uses the same investing style as every page.
"""

from typing import cast, get_args

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.upsert import upsert
from models import Preference, RatingState
from schemas import InvestingStyle

INVESTING_STYLE_KEY = "investing_style"
DEFAULT_STYLE: InvestingStyle = "investor"
_STYLES: tuple[str, ...] = get_args(InvestingStyle)


async def get_investing_style(session: AsyncSession) -> InvestingStyle:
    value = (
        await session.execute(
            select(Preference.value).where(Preference.key == INVESTING_STYLE_KEY)
        )
    ).scalar_one_or_none()
    return cast(InvestingStyle, value) if value in _STYLES else DEFAULT_STYLE


async def set_investing_style(session: AsyncSession, style: InvestingStyle) -> bool:
    """Persist the style. Returns True if it changed."""
    if style == await get_investing_style(session):
        return False
    await upsert(session, Preference, {"key": INVESTING_STYLE_KEY, "value": style}, keys=["key"])
    # Rating-change alerts compare against the last-seen rating. Ratings from the
    # other style aren't comparable, so drop the baselines (they are rebuilt on
    # the next evaluation) instead of firing a wave of "rating changed" alerts.
    await session.execute(delete(RatingState))
    await session.commit()
    return True


ASSISTANT_PERSONAL_KEY = "assistant_personal_data"


async def get_assistant_personal_data(session: AsyncSession) -> bool:
    """Whether the AI assistant may read the watchlist/portfolio (opt-in).
    Falls back to the `assistant_personal_data` setting until the user chooses."""
    from config import settings

    value = (
        await session.execute(
            select(Preference.value).where(Preference.key == ASSISTANT_PERSONAL_KEY)
        )
    ).scalar_one_or_none()
    return settings.assistant_personal_data if value is None else value == "true"


async def set_assistant_personal_data(session: AsyncSession, enabled: bool) -> None:
    value = "true" if enabled else "false"
    await upsert(session, Preference, {"key": ASSISTANT_PERSONAL_KEY, "value": value}, keys=["key"])
    await session.commit()
