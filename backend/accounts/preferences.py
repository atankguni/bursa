"""
accounts/preferences.py
-----------------------
Server-side preferences, per user. Stored in the DB (not the browser) so
background work (rating-change alerts) uses the same investing style as the
user's pages.
"""

import logging
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.models import User, UserSettings
from accounts.schemas import DisplaySettings, TradingCosts
from alerts.models import RatingState
from clock import as_utc
from db.upsert import upsert
from schemas import InvestingStyle

DEFAULT_STYLE: InvestingStyle = "investor"

log = logging.getLogger("bursa.preferences")


async def _row(session: AsyncSession, user_id: int) -> UserSettings | None:
    return await session.get(UserSettings, user_id, populate_existing=True)


async def _save(session: AsyncSession, user_id: int, **values: Any) -> None:  # noqa: ANN401
    """Set some settings of a user (creating the row with defaults). Does not commit."""
    await upsert(session, UserSettings, {"user_id": user_id, **values}, keys=["user_id"])


async def get_investing_style(session: AsyncSession, user_id: int) -> InvestingStyle:
    row = await _row(session, user_id)
    return row.investing_style if row else DEFAULT_STYLE


async def styles_by_user(session: AsyncSession, user_ids: set[int]) -> dict[int, InvestingStyle]:
    """Investing style of several users at once (default for those who never chose)."""
    rows = (
        await session.execute(
            select(UserSettings.user_id, UserSettings.investing_style).where(
                UserSettings.user_id.in_(user_ids)
            )
        )
    ).tuples().all()
    chosen: dict[int, InvestingStyle] = dict(rows)
    return {uid: chosen.get(uid, DEFAULT_STYLE) for uid in user_ids}


async def set_investing_style(session: AsyncSession, user_id: int, style: InvestingStyle) -> bool:
    """Persist the style. Returns True if it changed."""
    if style == await get_investing_style(session, user_id):
        return False
    await _save(session, user_id, investing_style=style)
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

    row = await _row(session, user_id)
    chosen = row.assistant_personal_data if row else None
    return settings.assistant_personal_data if chosen is None else chosen


async def set_assistant_personal_data(session: AsyncSession, user_id: int, enabled: bool) -> None:
    await _save(session, user_id, assistant_personal_data=enabled)
    await session.commit()


async def get_assistant_save_chats(session: AsyncSession, user_id: int) -> bool:
    """Whether assistant chats are saved so they can be continued (on by default)."""
    row = await _row(session, user_id)
    return row.assistant_save_chats if row else True


async def set_assistant_save_chats(session: AsyncSession, user_id: int, enabled: bool) -> None:
    """Turning saving off deletes the chats saved so far."""
    from assistant.chats import delete_all_chats

    await _save(session, user_id, assistant_save_chats=enabled)
    if not enabled:
        await delete_all_chats(session, user_id)
    await session.commit()


async def get_display(session: AsyncSession, user_id: int) -> DisplaySettings | None:
    """Saved display settings, or None if never saved (or no longer valid)."""
    row = await _row(session, user_id)
    if row is None or row.display is None:
        return None
    try:
        return DisplaySettings.model_validate(row.display)
    except ValidationError:
        log.warning("Ignoring invalid display settings of user %d", user_id)
        return None


async def set_display(session: AsyncSession, user_id: int, display: DisplaySettings) -> None:
    await _save(session, user_id, display=display.model_dump(mode="json", by_alias=True))
    await session.commit()


async def get_trading_costs(session: AsyncSession, user_id: int) -> TradingCosts:
    """The user's broker fee / tax rates (defaults until saved)."""
    row = await _row(session, user_id)
    if row is not None and row.trading_costs is not None:
        try:
            return TradingCosts.model_validate(row.trading_costs)
        except ValidationError:
            log.warning("Ignoring invalid trading costs of user %d", user_id)
    return TradingCosts()


async def set_trading_costs(session: AsyncSession, user_id: int, costs: TradingCosts) -> None:
    await _save(session, user_id, trading_costs=costs.model_dump(mode="json"))
    await session.commit()


async def get_daily_digest(session: AsyncSession, user_id: int) -> bool:
    """Opt-in: the daily summary email (alerts/digest.py)."""
    row = await _row(session, user_id)
    return row.daily_digest if row else False


async def set_daily_digest(session: AsyncSession, user_id: int, enabled: bool) -> None:
    await _save(session, user_id, daily_digest=enabled)
    await session.commit()


async def users_with_digest(session: AsyncSession) -> list[User]:
    """Active users who turned the daily summary on."""
    return list((
        await session.execute(
            select(User).join(UserSettings, UserSettings.user_id == User.id).where(
                UserSettings.daily_digest.is_(True),
                User.is_active.is_(True),
            )
        )
    ).scalars().all())


async def get_alerts_seen_at(session: AsyncSession, user_id: int) -> datetime | None:
    row = await _row(session, user_id)
    return row.alerts_seen_at if row else None


async def mark_alerts_seen(session: AsyncSession, user_id: int, up_to: datetime) -> None:
    """Alerts up to `up_to` were seen. Never moves back (another device may be behind)."""
    up_to = as_utc(up_to)
    current = await get_alerts_seen_at(session, user_id)
    if current is None or up_to > current:
        await _save(session, user_id, alerts_seen_at=up_to)
        await session.commit()
