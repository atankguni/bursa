"""Watchlist endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from models import Stock, Watchlist
from schemas import FundamentalOut, RecommendationSummary, WatchlistItemOut
from services.fundamentals import sync_many, sync_ticker
from services.metrics import derive_metrics
from services.prices import indices_map, latest_daily, latest_fundamentals
from services.recommendation import compute_universe

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


async def _build_watchlist(session: AsyncSession) -> list[WatchlistItemOut]:
    """Assemble watchlist rows (stock + price + fundamentals + ratios)."""
    links = (
        await session.execute(select(Watchlist).order_by(Watchlist.added_at))
    ).scalars().all()
    tickers = [w.ticker for w in links]
    if not tickers:
        return []

    stocks = (
        await session.execute(select(Stock).where(Stock.ticker.in_(tickers)))
    ).scalars().all()
    stock_map = {s.ticker: s for s in stocks}
    index_map = await indices_map(session, tickers)
    price_map = await latest_daily(session, tickers)
    fund_map = await latest_fundamentals(session, tickers)
    rec_map = await compute_universe(session)  # cross-sectional -> score everyone

    items: list[WatchlistItemOut] = []
    for link in links:
        stock = stock_map.get(link.ticker)
        if stock is None:
            continue
        info = price_map.get(link.ticker, {})
        last = info.get("close")
        prev = info.get("prev_close")
        change_pct = (
            round((last - prev) / prev * 100, 2)
            if last is not None and prev not in (None, 0)
            else None
        )
        f = fund_map.get(link.ticker)
        rec = rec_map.get(link.ticker)
        items.append(
            WatchlistItemOut(
                id=stock.id,
                ticker=stock.ticker,
                name=stock.name,
                indices=index_map.get(stock.ticker, []),
                added_at=link.added_at,
                last_price=last,
                change_percent=change_pct,
                fundamental=FundamentalOut.model_validate(f) if f else None,
                metrics=derive_metrics(last, f),
                recommendation=(
                    RecommendationSummary(
                        score=rec.score, rating=rec.rating, strength=rec.strength
                    )
                    if rec
                    else None
                ),
            )
        )
    return items


@router.get("", response_model=list[WatchlistItemOut])
async def get_watchlist(
    session: AsyncSession = Depends(get_session),
) -> list[WatchlistItemOut]:
    return await _build_watchlist(session)


@router.post("/refresh")
async def refresh_watchlist(
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Re-sync fundamentals for every watchlist ticker (on demand)."""
    tickers = (await session.execute(select(Watchlist.ticker))).scalars().all()
    rows = await sync_many(list(tickers), throttle=1.0)
    return {"tickers": len(tickers), "rows": rows}


@router.post(
    "/{ticker}",
    response_model=WatchlistItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_watchlist(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> WatchlistItemOut:
    """Add a ticker, fetching its fundamentals inline (best-effort)."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    existing = (
        await session.execute(
            select(Watchlist).where(Watchlist.ticker == ticker)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already on watchlist")

    session.add(Watchlist(ticker=ticker))
    await session.commit()

    # Populate fundamentals immediately so the new row is useful at once.
    await sync_ticker(ticker)

    items = await _build_watchlist(session)
    for item in items:
        if item.ticker == ticker:
            return item
    raise HTTPException(status_code=500, detail="Failed to build watchlist item")


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    link = (
        await session.execute(
            select(Watchlist).where(Watchlist.ticker == ticker)
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Not on watchlist")

    await session.delete(link)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
