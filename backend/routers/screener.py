"""Screener endpoint — rank/filter the tracked universe."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from deps import get_session
from schemas import ScreenerRow, SyncStartOut, SyncStatusOut
from services import sync_job
from services.screener import build_rows, filter_rows

router = APIRouter(prefix="/api", tags=["screener"])


@router.get("/screener", response_model=list[ScreenerRow])
async def screener(
    min_score: float | None = Query(None, description="Minimum recommendation score"),
    max_pbv: float | None = Query(None, description="Maximum price-to-book"),
    min_roe: float | None = Query(None, description="Minimum RoE (fraction, e.g. 0.15)"),
    rating: str | None = Query(None, description="Exact rating, e.g. 'Buy'"),
    sector: str | None = Query(None),
    buy_only: bool = Query(False, description="Only Buy / Strong Buy"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[ScreenerRow]:
    rows = await build_rows(session)
    rows = filter_rows(
        rows,
        min_score=min_score,
        max_pbv=max_pbv,
        min_roe=min_roe,
        rating=rating,
        sector=sector,
        buy_only=buy_only,
    )
    # Highest score first; stocks without a score sink to the bottom.
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return [ScreenerRow(**r) for r in rows[:limit]]


@router.get("/screener/sync/status", response_model=SyncStatusOut)
async def screener_sync_status() -> SyncStatusOut:
    """Progress of the background 'sync missing fundamentals' job."""
    return SyncStatusOut(**sync_job.status(), missing=await sync_job.missing_count())


@router.post("/screener/sync", response_model=SyncStartOut)
async def screener_sync(
    limit: int | None = Query(None, ge=1, le=200, description="Cap tickers per run"),
) -> SyncStartOut:
    """Queue a background fundamentals sync for stocks missing data."""
    missing = await sync_job.missing_tickers()
    cap = limit or settings.screener_sync_limit
    tickers = missing[:cap]
    if not tickers:
        return SyncStartOut(running=False, queued=0, total=0, remaining=0)

    started = sync_job.start(tickers)
    st = sync_job.status()
    return SyncStartOut(
        running=st["running"],
        queued=len(tickers) if started else 0,
        total=st["total"],
        remaining=st["remaining"],
    )
