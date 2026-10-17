"""Preference endpoints: the signed-in user's investing style, assistant access,
display settings and which alerts they have seen."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import current_user, get_session
from models import User
from schemas import PreferencesIn, PreferencesOut
from services.preferences import (
    get_alerts_seen_at,
    get_assistant_personal_data,
    get_display,
    get_investing_style,
    mark_alerts_seen,
    set_assistant_personal_data,
    set_display,
    set_investing_style,
)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


async def _current(session: AsyncSession, user: User) -> PreferencesOut:
    return PreferencesOut(
        investing_style=await get_investing_style(session, user.id),
        assistant_personal_data=await get_assistant_personal_data(session, user.id),
        display=await get_display(session, user.id),
        alerts_seen_at=await get_alerts_seen_at(session, user.id),
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
    if payload.display is not None:
        await set_display(session, user.id, payload.display)
    if payload.alerts_seen_at is not None:
        await mark_alerts_seen(session, user.id, payload.alerts_seen_at)
    return await _current(session, user)
