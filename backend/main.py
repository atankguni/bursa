"""
main.py
-------
FastAPI application for "Bursa" — personal IDX stock monitor.

Endpoints
~~~~~~~~~
GET /api/health
GET /api/stocks                          -> tracked stocks + latest price + change
GET /api/stocks/{ticker}/history         -> OHLCV bars for charting

Startup
~~~~~~~
* create SQLite tables (WAL enabled via database.engine event listener)
* seed the tracked-stock universe
* kick off the daily backfill then start the APScheduler worker
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, init_db
from models import Stock, StockPrice
from scheduler import backfill_daily, start_scheduler, stop_scheduler
from schemas import PricePoint, StockHistory, StockOut
from tickers import TRACKED_STOCKS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bursa")


# --------------------------------------------------------------------------- #
# Startup / shutdown
# --------------------------------------------------------------------------- #


async def _seed_stocks() -> None:
    """Insert the tracked universe once; keep existing rows untouched."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        existing = set(
            (await session.execute(select(Stock.ticker))).scalars().all()
        )
        new_rows = [
            Stock(**s) for s in TRACKED_STOCKS if s["ticker"] not in existing
        ]
        if new_rows:
            session.add_all(new_rows)
            await session.commit()
            log.info("Seeded %d new stocks", len(new_rows))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB -> seed -> backfill -> start scheduler."""
    await init_db()
    await _seed_stocks()

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
    version="1.0.0",
    lifespan=lifespan,
)

# Permissive CORS for local dev (Vite runs on :5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/api/stocks", response_model=list[StockOut])
async def list_stocks(session: AsyncSession = Depends(get_session)) -> list[StockOut]:
    """
    List every tracked stock with its latest daily close and the change versus
    the previous close (absolute points + percent).
    """
    stocks = (await session.execute(select(Stock).order_by(Stock.ticker))).scalars().all()

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
        select(StockPrice.ticker, StockPrice.close, StockPrice.volume,
               StockPrice.timestamp, rn)
        .where(StockPrice.interval == "1d")
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
                index_name=stock.index_name,
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
    points = [
        PricePoint.model_validate(p) for p in reversed(prices)
    ]

    return StockHistory(
        ticker=stock.ticker,
        name=stock.name,
        index_name=stock.index_name,
        interval=interval,
        points=points,
    )
