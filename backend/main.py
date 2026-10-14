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

Startup
~~~~~~~
* create SQLite tables (WAL enabled via database.engine event listener)
* seed the tracked-stock universe + index memberships
* kick off the daily backfill then start the APScheduler worker
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, init_db
from models import Stock, StockIndex, StockPrice
from scheduler import backfill_daily, start_scheduler, stop_scheduler
from schemas import PricePoint, StockHistory, StockOut
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


@app.get("/api/stocks", response_model=list[StockOut])
async def list_stocks(
    index: str | None = Query(None, description="Filter by index name, e.g. LQ45"),
    session: AsyncSession = Depends(get_session),
) -> list[StockOut]:
    """
    List tracked stocks (optionally filtered to one index) with the latest
    daily close and the change versus the previous close.
    """
    stmt = select(Stock).order_by(Stock.ticker)
    if index:
        stmt = stmt.join(
            StockIndex, StockIndex.ticker == Stock.ticker
        ).where(StockIndex.index_name == index)
    stocks = (await session.execute(stmt)).scalars().all()
    tickers = [s.ticker for s in stocks]
    index_map = await _indices_map(session, tickers)

    # Window function: rank the two most recent daily bars per ticker.
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
