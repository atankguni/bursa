"""Health + metadata endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from deps import get_session
from market.providers.governor import governor
from market.providers.registry import available as available_providers
from market.sync import last_synced_at
from market.tickers import INDEX_ORDER
from models import Stock, StockIndex
from schemas import MarketStatusOut, ProviderInfo, ProvidersOut, StatusOut
from services.market_clock import status as market_status

router = APIRouter(prefix="/api", tags=["meta"])
# Liveness probe for Docker / uptime checks: the one endpoint needing no sign-in.
public = APIRouter(prefix="/api", tags=["meta"])


@public.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status", response_model=StatusOut)
async def get_status(session: AsyncSession = Depends(get_session)) -> StatusOut:
    """Global status for the app footer (sync time, provider, session, ...)."""
    st = market_status()
    tracked = (
        await session.execute(select(func.count()).select_from(Stock))
    ).scalar_one()
    calls = {name: s.calls_today for name, s in governor.stats().items()}
    return StatusOut(
        server_time=st.server_time,
        timezone=st.timezone,
        session=st.session,
        last_sync=last_synced_at(),
        stocks_tracked=int(tracked),
        providers={
            "price": settings.price_provider,
            "fundamentals": settings.fundamentals_provider,
        },
        calls_today=calls,
        lot_size=settings.lot_size,
    )


@router.get("/market-status", response_model=MarketStatusOut)
async def get_market_status() -> MarketStatusOut:
    """Current IDX trading state (drives the navbar indicator)."""
    return market_status()


@router.get("/providers", response_model=ProvidersOut)
async def get_providers() -> ProvidersOut:
    """Active data providers + the full registry (read-only)."""
    return ProvidersOut(
        price=settings.price_provider,
        fundamentals=settings.fundamentals_provider,
        available=[ProviderInfo(**p) for p in available_providers()],
        metrics=governor.stats(),
    )


@router.get("/indexes", response_model=list[str])
async def list_indexes(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Distinct index names present in the DB, ordered for the UI selector."""
    rows = (
        await session.execute(select(StockIndex.index_name).distinct())
    ).scalars().all()
    known = [i for i in INDEX_ORDER if i in rows]
    extra = sorted(set(rows) - set(INDEX_ORDER))
    return known + extra
