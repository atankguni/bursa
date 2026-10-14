"""Health + metadata endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from market.tickers import INDEX_ORDER
from models import StockIndex

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/indexes", response_model=list[str])
async def list_indexes(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Distinct index names present in the DB, ordered for the UI selector."""
    rows = (
        await session.execute(select(StockIndex.index_name).distinct())
    ).scalars().all()
    known = [i for i in INDEX_ORDER if i in rows]
    extra = sorted(set(rows) - set(INDEX_ORDER))
    return known + extra
