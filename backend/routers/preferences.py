"""User preference endpoints (investing style)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from schemas import PreferencesIn, PreferencesOut
from services.preferences import get_investing_style, set_investing_style
from services.recommendation import invalidate_cache

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesOut)
async def get_preferences(session: AsyncSession = Depends(get_session)) -> PreferencesOut:
    return PreferencesOut(investing_style=await get_investing_style(session))


@router.put("", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesIn, session: AsyncSession = Depends(get_session)
) -> PreferencesOut:
    """Save preferences; switching investing style re-scores every stock."""
    if await set_investing_style(session, payload.investing_style):
        invalidate_cache()
    return PreferencesOut(investing_style=payload.investing_style)
