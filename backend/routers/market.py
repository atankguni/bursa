"""Market overview endpoint (breadth, movers, sectors)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from schemas import MarketOverviewOut, MoverOut, SectorOut
from services.market_overview import overview

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview", response_model=MarketOverviewOut)
async def get_overview(session: AsyncSession = Depends(get_session)) -> MarketOverviewOut:
    data = await overview(session)
    return MarketOverviewOut(
        up=data["up"],
        down=data["down"],
        flat=data["flat"],
        top_gainers=[MoverOut(**m) for m in data["top_gainers"]],
        top_losers=[MoverOut(**m) for m in data["top_losers"]],
        sectors=[SectorOut(**s) for s in data["sectors"]],
    )
