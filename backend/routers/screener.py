"""Screener endpoint — rank/filter the tracked universe."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from deps import get_session, require_admin, user_style
from schemas import InvestingStyle, ScreenerPage, SyncStartOut, SyncStatusOut
from services import sync_job
from services.screener import build_rows, filter_rows

router = APIRouter(prefix="/api", tags=["screener"])


@router.get("/screener", response_model=ScreenerPage)
async def screener(
    min_score: float | None = Query(None, description="Minimum recommendation score"),
    max_pbv: float | None = Query(None, description="Maximum price-to-book"),
    min_roe: float | None = Query(None, description="Minimum RoE (fraction, e.g. 0.15)"),
    rating: str | None = Query(None, description="Exact rating, e.g. 'Buy'"),
    sector: str | None = Query(None),
    buy_only: bool = Query(False, description="Only Buy / Strong Buy"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    style: InvestingStyle = Depends(user_style),
) -> ScreenerPage:
    """Rank/filter the whole universe, one page at a time (`total` = all matches)."""
    rows = await build_rows(session, style)
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
    # Highest score first, then stocks with data before blanks, then by ticker,
    # so the order is stable across pages.
    rows.sort(key=lambda r: (r.score is None, -(r.score or 0), r.pbv is None, r.ticker))
    return ScreenerPage(
        items=rows[offset : offset + limit],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


async def _sync_status() -> SyncStatusOut:
    status = sync_job.status()
    status.missing = await sync_job.missing_count()
    return status


@router.get("/screener/sync/status", response_model=SyncStatusOut)
async def screener_sync_status() -> SyncStatusOut:
    """Progress of the background 'sync missing fundamentals' job."""
    return await _sync_status()


@router.post(
    "/screener/sync",
    response_model=SyncStartOut,
    dependencies=[Depends(require_admin)],  # provider calls for the whole universe
)
async def screener_sync(
    limit: int | None = Query(None, ge=1, le=200, description="Cap tickers per run"),
    all_missing: bool = Query(
        False, alias="all",
        description="Work through every never-tried stock in paced batches",
    ),
) -> SyncStartOut:
    """Queue a background fundamentals sync for stocks missing data."""
    if all_missing:
        started = await sync_job.start_all()
        st = sync_job.status()
        return SyncStartOut(
            running=st.running, queued=st.total if started else 0,
            total=st.total, remaining=st.remaining,
        )
    missing = await sync_job.missing_tickers()
    cap = limit or settings.screener_sync_limit
    tickers = missing[:cap]
    if not tickers:
        return SyncStartOut(running=False, queued=0, total=0, remaining=0)

    started = sync_job.start(tickers)
    st = sync_job.status()
    return SyncStartOut(
        running=st.running,
        queued=len(tickers) if started else 0,
        total=st.total,
        remaining=st.remaining,
    )


@router.post(
    "/screener/sync/cancel", response_model=SyncStatusOut, dependencies=[Depends(require_admin)]
)
async def screener_sync_cancel() -> SyncStatusOut:
    """Stop the running sync after the current stock."""
    sync_job.cancel()
    return await _sync_status()
