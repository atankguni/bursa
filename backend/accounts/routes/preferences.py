"""Preference endpoints: the signed-in user's investing style, assistant access,
display settings and which alerts they have seen."""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from accounts.auth import AuthError, lock_minutes
from accounts.models import User
from accounts.preferences import (
    get_alerts_seen_at,
    get_assistant_personal_data,
    get_assistant_save_chats,
    get_daily_digest,
    get_display,
    get_investing_style,
    get_trading_costs,
    mark_alerts_seen,
    set_assistant_personal_data,
    set_assistant_save_chats,
    set_daily_digest,
    set_display,
    set_investing_style,
    set_lock_minutes,
    set_trading_costs,
)
from accounts.schemas import PreferencesIn, PreferencesOut
from alerts.digest import send_digest
from clock import local_today
from deps import current_user, get_session

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


async def _current(session: AsyncSession, user: User) -> PreferencesOut:
    return PreferencesOut(
        investing_style=await get_investing_style(session, user.id),
        assistant_personal_data=await get_assistant_personal_data(session, user.id),
        assistant_save_chats=await get_assistant_save_chats(session, user.id),
        display=await get_display(session, user.id),
        alerts_seen_at=await get_alerts_seen_at(session, user.id),
        trading_costs=await get_trading_costs(session, user.id),
        daily_digest=await get_daily_digest(session, user.id),
        lock_minutes=await lock_minutes(session, user),
    )


@router.get("", response_model=PreferencesOut)
async def get_preferences(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> PreferencesOut:
    return await _current(session, user)


@router.put("", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> PreferencesOut:
    """Save the fields sent. Scores are cached per style, so switching needs no
    cache reset (and doesn't disturb other users)."""
    if payload.investing_style is not None:
        await set_investing_style(session, user.id, payload.investing_style)
    if payload.assistant_personal_data is not None:
        await set_assistant_personal_data(session, user.id, payload.assistant_personal_data)
    if payload.assistant_save_chats is not None:
        await set_assistant_save_chats(session, user.id, payload.assistant_save_chats)
    if payload.display is not None:
        await set_display(session, user.id, payload.display)
    if payload.alerts_seen_at is not None:
        await mark_alerts_seen(session, user.id, payload.alerts_seen_at)
    if payload.trading_costs is not None:
        await set_trading_costs(session, user.id, payload.trading_costs)
    if payload.daily_digest is not None:
        await set_daily_digest(session, user.id, payload.daily_digest)
    if payload.lock_minutes is not None:
        try:
            await set_lock_minutes(session, user, payload.lock_minutes)
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _current(session, user)


@router.post("/digest/preview", status_code=202)
async def send_digest_now(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> dict[str, str]:
    """Email today's summary now (to check how it looks)."""
    if not mail.configured():
        raise HTTPException(status_code=409, detail="Email isn't set up on this server")
    day = local_today()
    if not await send_digest(session, user, day):
        raise HTTPException(
            status_code=409,
            detail="Nothing to send: add stocks to your watchlist or portfolio first",
        )
    return {"status": "sent"}
