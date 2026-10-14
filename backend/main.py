"""
main.py
-------
FastAPI application for "Bursa" — personal IDX stock monitor.

Endpoints
~~~~~~~~~
GET /api/health
GET /api/indexes                         -> available index names (for the UI select)
GET /api/stocks?index=LQ45               -> constituents + latest price + change
GET /api/stocks/{ticker}/history         -> OHLCV bars for charting
GET /api/stocks/{ticker}/fundamentals    -> yearly fundamentals + PBV/RoE
GET /api/watchlist                       -> watchlist with price + fundamentals + ratios
POST /api/watchlist/{ticker}             -> add a ticker to the watchlist
DELETE /api/watchlist/{ticker}           -> remove a ticker from the watchlist
POST /api/watchlist/refresh              -> re-sync all watchlist fundamentals

Startup
~~~~~~~
* create SQLite tables (WAL enabled via database.engine event listener)
* seed the tracked-stock universe + index memberships
* kick off the daily backfill then start the APScheduler worker
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, init_db
from fundamentals import sync_many, sync_ticker
from models import Fundamental, Stock, StockIndex, StockPrice, Watchlist
from scheduler import backfill_daily, start_scheduler, stop_scheduler
from schemas import (
    DerivedMetrics,
    FundamentalOut,
    FundamentalsResponse,
    PricePoint,
    StockHistory,
    StockOut,
    WatchlistItemOut,
)
from tickers import INDEX_ORDER, all_tickers, associations, name_for

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bursa")


# --------------------------------------------------------------------------- #
# Startup / shutdown
# --------------------------------------------------------------------------- #


async def _seed() -> None:
    """Seed stocks + index memberships once; existing rows are left untouched."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        existing = set(
            (await session.execute(select(Stock.ticker))).scalars().all()
        )
        new_stocks = [
            Stock(ticker=t, name=name_for(t))
            for t in all_tickers()
            if t not in existing
        ]
        if new_stocks:
            session.add_all(new_stocks)
            await session.flush()

        existing_links = set(
            (await session.execute(
                select(StockIndex.ticker, StockIndex.index_name)
            )).all()
        )
        new_links = [
            StockIndex(ticker=t, index_name=idx)
            for t, idx in associations()
            if (t, idx) not in existing_links
        ]
        if new_links:
            session.add_all(new_links)

        if new_stocks or new_links:
            await session.commit()
            log.info(
                "Seeded %d stocks, %d index links",
                len(new_stocks), len(new_links),
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB -> seed -> backfill -> start scheduler."""
    await init_db()
    await _seed()

    # Blocking initial backfill so charts have data immediately after boot.
    await backfill_daily()

    start_scheduler()
    log.info("Bursa API ready")
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="Bursa API",
    description="Personal IDX (Indonesian stock exchange) monitoring backend.",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS for local dev. NOTE: wildcard "*" + allow_credentials=True is invalid
# per the CORS spec and browsers reject it, so we list explicit origins.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/indexes", response_model=list[str])
async def list_indexes(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Distinct index names present in the DB, ordered for the UI selector."""
    rows = (
        await session.execute(select(StockIndex.index_name).distinct())
    ).scalars().all()
    known = [i for i in INDEX_ORDER if i in rows]
    extra = sorted(set(rows) - set(INDEX_ORDER))
    return known + extra


async def _indices_map(
    session: AsyncSession, tickers: list[str]
) -> dict[str, list[str]]:
    """Return {ticker: [index, ...]} ordered by INDEX_ORDER."""
    if not tickers:
        return {}
    rows = (
        await session.execute(
            select(StockIndex.ticker, StockIndex.index_name).where(
                StockIndex.ticker.in_(tickers)
            )
        )
    ).all()
    mapping: dict[str, list[str]] = {}
    for ticker, index_name in rows:
        mapping.setdefault(ticker, []).append(index_name)
    order = {name: i for i, name in enumerate(INDEX_ORDER)}
    for ticker in mapping:
        mapping[ticker].sort(key=lambda n: order.get(n, 999))
    return mapping


async def _latest_daily(session: AsyncSession, tickers: list[str]) -> dict[str, dict]:
    """Map each ticker to its latest daily close (+ prev close, volume, time)."""
    if not tickers:
        return {}
    rn = (
        func.row_number()
        .over(
            partition_by=StockPrice.ticker,
            order_by=StockPrice.timestamp.desc(),
        )
        .label("rn")
    )
    ranked = (
        select(
            StockPrice.ticker, StockPrice.close, StockPrice.volume,
            StockPrice.timestamp, rn,
        )
        .where(StockPrice.interval == "1d", StockPrice.ticker.in_(tickers))
        .subquery()
    )
    recent = (
        select(ranked)
        .where(ranked.c.rn <= 2)
        .order_by(ranked.c.ticker, ranked.c.rn)
    )
    rows = (await session.execute(recent)).all()

    latest: dict[str, dict] = {}
    for ticker, close, volume, ts, rank in rows:
        entry = latest.setdefault(ticker, {})
        if rank == 1:
            entry["close"] = close
            entry["volume"] = volume
            entry["updated_at"] = ts
        else:
            entry["prev_close"] = close
    return latest


async def _latest_fundamentals(
    session: AsyncSession, tickers: list[str]
) -> dict[str, Fundamental]:
    """Map each ticker to its most recent fiscal-year Fundamental row."""
    if not tickers:
        return {}
    rows = (
        await session.execute(
            select(Fundamental).where(Fundamental.ticker.in_(tickers))
        )
    ).scalars().all()
    best: dict[str, Fundamental] = {}
    for f in rows:
        cur = best.get(f.ticker)
        if cur is None or f.fiscal_year > cur.fiscal_year:
            best[f.ticker] = f
    return best


def _derived(price: float | None, f: Fundamental | None) -> DerivedMetrics:
    """Compute market cap, book value, PBV and RoE from price + fundamentals."""
    if f is None:
        return DerivedMetrics()

    market_cap = (
        price * f.total_shares
        if price is not None and f.total_shares
        else None
    )

    book_value = None
    if f.total_assets is not None and f.total_liabilities is not None:
        book_value = f.total_assets - f.total_liabilities
    elif f.equity is not None:
        book_value = f.equity

    pbv = (
        round(market_cap / book_value, 3)
        if market_cap and book_value and book_value > 0
        else None
    )
    roe = (
        round(f.net_income / f.equity, 4)
        if f.net_income is not None and f.equity not in (None, 0)
        else None
    )
    return DerivedMetrics(
        market_cap=market_cap, book_value=book_value, pbv=pbv, roe=roe
    )


@app.get("/api/stocks", response_model=list[StockOut])
async def list_stocks(
    index: list[str] | None = Query(
        None, description="Filter by one or more index names, e.g. index=LQ45&index=IDX30"
    ),
    session: AsyncSession = Depends(get_session),
) -> list[StockOut]:
    """
    List tracked stocks (optionally filtered to one or more indices) with the
    latest daily close and the change versus the previous close.
    """
    stmt = select(Stock).order_by(Stock.ticker)
    if index:
        # De-duplicate the incoming list so the HAVING count is accurate.
        wanted = list(dict.fromkeys(index))
        # Intersection: keep only stocks that belong to EVERY selected index.
        stmt = (
            stmt.join(StockIndex, StockIndex.ticker == Stock.ticker)
            .where(StockIndex.index_name.in_(wanted))
            .group_by(Stock.id)
            .having(
                func.count(func.distinct(StockIndex.index_name)) == len(wanted)
            )
        )
    stocks = (await session.execute(stmt)).scalars().all()
    tickers = [s.ticker for s in stocks]
    index_map = await _indices_map(session, tickers)
    latest = await _latest_daily(session, tickers)

    result: list[StockOut] = []
    for stock in stocks:
        info = latest.get(stock.ticker, {})
        last = info.get("close")
        prev = info.get("prev_close")
        change = None
        change_pct = None
        if last is not None and prev is not None and prev != 0:
            change = round(last - prev, 2)
            change_pct = round((last - prev) / prev * 100, 2)

        result.append(
            StockOut(
                id=stock.id,
                ticker=stock.ticker,
                name=stock.name,
                indices=index_map.get(stock.ticker, []),
                last_price=last,
                previous_close=prev,
                change=change,
                change_percent=change_pct,
                volume=info.get("volume"),
                updated_at=info.get("updated_at"),
            )
        )
    return result


@app.get("/api/stocks/{ticker}/history", response_model=StockHistory)
async def stock_history(
    ticker: str,
    interval: str = Query("1d", pattern="^(1d|1m)$"),
    limit: int = Query(365, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> StockHistory:
    """Return ascending OHLCV bars for one ticker (daily or 1-minute)."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    # Grab the newest `limit` bars, then reverse to chronological order.
    stmt = (
        select(StockPrice)
        .where(StockPrice.ticker == ticker, StockPrice.interval == interval)
        .order_by(StockPrice.timestamp.desc())
        .limit(limit)
    )
    prices = (await session.execute(stmt)).scalars().all()
    points = [PricePoint.model_validate(p) for p in reversed(prices)]

    index_map = await _indices_map(session, [ticker])
    return StockHistory(
        ticker=stock.ticker,
        name=stock.name,
        indices=index_map.get(ticker, []),
        interval=interval,
        points=points,
    )


@app.get(
    "/api/stocks/{ticker}/fundamentals",
    response_model=FundamentalsResponse,
)
async def stock_fundamentals(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> FundamentalsResponse:
    """Yearly fundamentals for one ticker plus PBV/RoE vs the latest price."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    rows = (
        await session.execute(
            select(Fundamental)
            .where(Fundamental.ticker == ticker)
            .order_by(Fundamental.fiscal_year)
        )
    ).scalars().all()

    price_map = await _latest_daily(session, [ticker])
    price = price_map.get(ticker, {}).get("close")
    latest_row = rows[-1] if rows else None

    return FundamentalsResponse(
        ticker=stock.ticker,
        name=stock.name,
        yearly=[FundamentalOut.model_validate(r) for r in rows],
        latest=FundamentalOut.model_validate(latest_row) if latest_row else None,
        metrics=_derived(price, latest_row),
    )


# --------------------------------------------------------------------------- #
# Watchlist
# --------------------------------------------------------------------------- #


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
    index_map = await _indices_map(session, tickers)
    price_map = await _latest_daily(session, tickers)
    fund_map = await _latest_fundamentals(session, tickers)

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
                metrics=_derived(last, f),
            )
        )
    return items


@app.get("/api/watchlist", response_model=list[WatchlistItemOut])
async def get_watchlist(
    session: AsyncSession = Depends(get_session),
) -> list[WatchlistItemOut]:
    return await _build_watchlist(session)


@app.post("/api/watchlist/refresh")
async def refresh_watchlist(
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Re-sync fundamentals for every watchlist ticker (on demand)."""
    tickers = (
        await session.execute(select(Watchlist.ticker))
    ).scalars().all()
    rows = await sync_many(list(tickers), throttle=1.0)
    return {"tickers": len(tickers), "rows": rows}


@app.post(
    "/api/watchlist/{ticker}",
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


@app.delete("/api/watchlist/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
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
