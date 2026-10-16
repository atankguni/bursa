"""User preference endpoints (investing style)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from schemas import PreferencesIn, PreferencesOut
from services.preferences import (
    get_assistant_personal_data,
    get_investing_style,
    set_assistant_personal_data,
    set_investing_style,
)
from services.recommendation import invalidate_cache

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


async def _current(session: AsyncSession) -> PreferencesOut:
    return PreferencesOut(
        investing_style=await get_investing_style(session),
        assistant_personal_data=await get_assistant_personal_data(session),
    )


@router.get("", response_model=PreferencesOut)
async def get_preferences(session: AsyncSession = Depends(get_session)) -> PreferencesOut:
    return await _current(session)


@router.put("", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesIn, session: AsyncSession = Depends(get_session)
) -> PreferencesOut:
    """Save the fields sent; switching investing style re-scores every stock."""
    if payload.investing_style is not None and await set_investing_style(
        session, payload.investing_style
    ):
        invalidate_cache()
    if payload.assistant_personal_data is not None:
        await set_assistant_personal_data(session, payload.assistant_personal_data)
    return await _current(session)
