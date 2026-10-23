"""Watchlist endpoints (the signed-in user's list)."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.models import User
from deps import current_user, get_session, require_admin, user_style
from market.fundamentals import sync_many, sync_ticker
from market.metrics import derive_metrics
from market.models import Stock
from market.prices import indices_map, latest_daily, latest_fundamentals
from market.schemas import FundamentalOut
from portfolio.models import Watchlist
from portfolio.schemas import WatchlistItemOut
from schemas import InvestingStyle, StockCode
from signals.recommendation import compute_universe_cached, invalidate_cache
from signals.schemas import RecommendationSummary

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


async def _build_watchlist(
    session: AsyncSession, user_id: int, style: InvestingStyle
) -> list[WatchlistItemOut]:
    """Assemble one user's watchlist rows (stock + price + fundamentals + ratios)."""
    links = (
        await session.execute(
            select(Watchlist).where(Watchlist.user_id == user_id).order_by(Watchlist.added_at)
        )
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
    rec_map = await compute_universe_cached(session, style)  # cross-sectional

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
                ticker=stock.ticker,
                name=stock.name,
                board=stock.listing_board,
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
    user: User = Depends(current_user),
    style: InvestingStyle = Depends(user_style),
) -> list[WatchlistItemOut]:
    return await _build_watchlist(session, user.id, style)


@router.post("/refresh")
async def refresh_watchlist(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),  # provider calls; everyone's lists refresh daily
) -> dict[str, int]:
    """Re-sync fundamentals for the admin's watchlist tickers (on demand)."""
    tickers = (
        await session.execute(select(Watchlist.ticker).where(Watchlist.user_id == user.id))
    ).scalars().all()
    rows = await sync_many(list(tickers), throttle=1.0)
    await invalidate_cache()  # fresh fundamentals -> recompute scores next request
    return {"tickers": len(tickers), "rows": rows}


@router.post(
    "/{ticker}",
    response_model=WatchlistItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_watchlist(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
    style: InvestingStyle = Depends(user_style),
) -> WatchlistItemOut:
    """Add a ticker, fetching its fundamentals inline (best-effort)."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    existing = (
        await session.execute(
            select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.ticker == ticker)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already on watchlist")

    session.add(Watchlist(user_id=user.id, ticker=ticker))
    await session.commit()

    # Populate fundamentals immediately so the new row is useful at once.
    await sync_ticker(ticker)
    await invalidate_cache()

    items = await _build_watchlist(session, user.id, style)
    for item in items:
        if item.ticker == ticker:
            return item
    raise HTTPException(status_code=500, detail="Failed to build watchlist item")


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> Response:
    link = (
        await session.execute(
            select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.ticker == ticker)
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Not on watchlist")

    await session.delete(link)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
