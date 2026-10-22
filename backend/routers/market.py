"""Market overview endpoint (breadth, movers, sectors)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from schemas import MarketOverviewOut
from services.market_overview import overview

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview", response_model=MarketOverviewOut)
async def get_overview(session: AsyncSession = Depends(get_session)) -> MarketOverviewOut:
    return await overview(session)
