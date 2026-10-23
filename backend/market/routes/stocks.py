"""Stock listing, price history and fundamentals endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from clock import day_key
from deps import get_session, require_admin, user_style
from market.corporate_actions import load_splits
from market.dividends import list_dividends, trailing_dps
from market.fundamentals import is_stale, sync_ticker
from market.history import DEEP_RANGES, ensure_full_history, range_start
from market.metrics import derive_metrics
from market.models import DailyBar, Fundamental, IntradayBar, Stock, StockIndex, StockProfile
from market.prices import indices_map, latest_daily
from market.schemas import (
    CatalogPage,
    CatalogRow,
    CompanyOut,
    DividendOut,
    DividendSummary,
    FundamentalOut,
    FundamentalsResponse,
    OfficerOut,
    PricePoint,
    SearchResultOut,
    SplitOut,
    StockHistory,
    StockOut,
    TrackStockIn,
)
from market.search import search
from schemas import InvestingStyle, StockCode
from signals.recommendation import compute_universe_cached
from signals.schemas import RecommendationOut, RecommendationSummary, TrackRecordOut, ValuationOut
from signals.track_record import HORIZON, live_record, load_backtest
from signals.valuation import valuation

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/search", response_model=list[SearchResultOut])
async def search_symbols(
    q: str = Query(..., min_length=2, max_length=40),
    all_exchanges: bool = Query(False, alias="all"),
) -> list[SearchResultOut]:
    """Resolve a free-text query to candidate symbols (IDX-only unless `all`)."""
    hits = await search(q, idf_only=not all_exchanges)
    return [
        SearchResultOut(symbol=h["symbol"], name=h["name"], exchange=h["exchange"], type=h["type"])
        for h in hits
    ]


@router.post(
    "/stocks",
    response_model=StockOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],  # grows the shared universe (provider calls)
)
async def track_stock(
    payload: TrackStockIn,
    session: AsyncSession = Depends(get_session),
) -> StockOut:
    """Add an IDX stock that isn't in the catalog yet (e.g. a new listing)."""
    ticker = payload.ticker
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    existing = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already tracked")

    stock = Stock(ticker=ticker, name=payload.name or ticker)
    session.add(stock)
    await session.commit()
    return StockOut(ticker=stock.ticker, name=stock.name)


@router.get("/stocks", response_model=list[StockOut])
async def list_stocks(
    index: list[str] | None = Query(
        None,
        description="Filter by one or more index names, e.g. index=LQ45&index=IDX30",
    ),
    session: AsyncSession = Depends(get_session),
    style: InvestingStyle = Depends(user_style),
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
            .where(StockIndex.index_code.in_(wanted))
            .group_by(Stock.ticker)
            .having(
                func.count(func.distinct(StockIndex.index_code)) == len(wanted)
            )
        )
    stocks = (await session.execute(stmt)).scalars().all()
    tickers = [s.ticker for s in stocks]
    index_map = await indices_map(session, tickers)
    latest = await latest_daily(session, tickers)
    rec_map = await compute_universe_cached(session, style)  # cross-sectional, cached

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

        rec = rec_map.get(stock.ticker)
        result.append(
            StockOut(
                ticker=stock.ticker,
                name=stock.name,
                board=stock.listing_board,
                indices=index_map.get(stock.ticker, []),
                last_price=last,
                previous_close=prev,
                change=change,
                change_percent=change_pct,
                volume=info.get("volume"),
                updated_at=info.get("updated_at"),
                recommendation=(
                    RecommendationSummary(
                        score=rec.score, rating=rec.rating, strength=rec.strength
                    )
                    if rec
                    else None
                ),
            )
        )
    return result


@router.get("/stocks/{ticker}", response_model=StockOut)
async def get_stock(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
    style: InvestingStyle = Depends(user_style),
) -> StockOut:
    """Summary for a single tracked stock (price, change, indices, signal)."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    info = (await latest_daily(session, [ticker])).get(ticker, {})
    last = info.get("close")
    prev = info.get("prev_close")
    change = None
    change_pct = None
    if last is not None and prev is not None and prev != 0:
        change = round(last - prev, 2)
        change_pct = round((last - prev) / prev * 100, 2)

    index_map = await indices_map(session, [ticker])
    rec = (await compute_universe_cached(session, style)).get(ticker)

    return StockOut(
        ticker=stock.ticker,
        name=stock.name,
        board=stock.listing_board,
        indices=index_map.get(ticker, []),
        last_price=last,
        previous_close=prev,
        change=change,
        change_percent=change_pct,
        volume=info.get("volume"),
        updated_at=info.get("updated_at"),
        recommendation=(
            RecommendationSummary(
                score=rec.score, rating=rec.rating, strength=rec.strength
            )
            if rec
            else None
        ),
    )


@router.get("/stocks/{ticker}/history", response_model=StockHistory)
async def stock_history(
    ticker: StockCode,
    interval: str = Query("1d", pattern="^(1d|1m)$"),
    limit: int = Query(365, ge=1, le=2000),
    range_: str | None = Query(
        None,
        alias="range",
        pattern="^(1m|3m|6m|1y|5y|max)$",
        description="Daily bars covering this span (5y/max fetch full history once). "
        "Overrides `limit`.",
    ),
    session: AsyncSession = Depends(get_session),
) -> StockHistory:
    """Return ascending OHLCV bars for one ticker (daily or 1-minute)."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    if interval == "1d":
        stmt = select(DailyBar).where(DailyBar.ticker == ticker)
        if range_ is not None:
            if range_ in DEEP_RANGES:
                await ensure_full_history(session, stock, range_)
            start = range_start(range_)
            if start is not None:
                stmt = stmt.where(DailyBar.day >= start.date())
            bars = (await session.execute(stmt.order_by(DailyBar.day))).scalars().all()
        else:
            # The newest `limit` bars, in chronological order.
            newest = stmt.order_by(DailyBar.day.desc()).limit(limit)
            bars = list(reversed((await session.execute(newest)).scalars().all()))
        points = [
            PricePoint(
                timestamp=day_key(b.day), open=b.open, high=b.high, low=b.low,
                close=b.close, volume=b.volume,
            )
            for b in bars
        ]
    else:
        stmt = (
            select(IntradayBar)
            .where(IntradayBar.ticker == ticker)
            .order_by(IntradayBar.timestamp.desc())
            .limit(limit)
        )
        minutes = (await session.execute(stmt)).scalars().all()
        points = [PricePoint.model_validate(p) for p in reversed(minutes)]

    index_map = await indices_map(session, [ticker])
    splits = (await load_splits(session, [ticker]))[ticker]
    return StockHistory(
        ticker=stock.ticker,
        name=stock.name,
        indices=index_map.get(ticker, []),
        interval=interval,
        points=points,
        splits=[SplitOut(ex_date=d, ratio=r) for d, r in splits],
    )


@router.get(
    "/stocks/{ticker}/fundamentals",
    response_model=FundamentalsResponse,
)
async def stock_fundamentals(
    ticker: StockCode,
    refresh: bool = Query(False, description="Force a re-fetch from the provider"),
    session: AsyncSession = Depends(get_session),
) -> FundamentalsResponse:
    """
    Yearly fundamentals for one ticker plus PBV/RoE vs the latest price.

    Works for ANY tracked stock, not just watchlist members: if nothing is
    cached (or the cache is stale, or ``refresh=true``) the data is fetched
    from the data provider on demand and cached for subsequent requests.
    """
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    async def load() -> list[Fundamental]:
        result = await session.execute(
            select(Fundamental)
            .where(Fundamental.ticker == ticker)
            .order_by(Fundamental.fiscal_year)
        )
        return list(result.scalars().all())

    rows = await load()

    if refresh or is_stale(rows):
        # sync_ticker writes via its own session; end ours so the re-read
        # observes the committed rows rather than a stale snapshot.
        await sync_ticker(ticker)
        await session.commit()
        rows = await load()

    price_map = await latest_daily(session, [ticker])
    price = price_map.get(ticker, {}).get("close")
    latest_row = rows[-1] if rows else None

    return FundamentalsResponse(
        ticker=stock.ticker,
        name=stock.name,
        yearly=[FundamentalOut.model_validate(r) for r in rows],
        latest=FundamentalOut.model_validate(latest_row) if latest_row else None,
        metrics=derive_metrics(price, latest_row),
    )


@router.get("/stocks/{ticker}/recommendation", response_model=RecommendationOut)
async def stock_recommendation(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
    style: InvestingStyle = Depends(user_style),
) -> RecommendationOut:
    """
    Buy-signal score for one ticker.

    Scores are relative to the tracked universe, so we score everyone and return
    the requested ticker.
    """
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    rec = (await compute_universe_cached(session, style)).get(ticker)
    if rec is None:
        # Eligibility differs per style (see signals/recommendation._eligible).
        need = (
            "it is too thinly traded or has under 21 days of prices"
            if style == "trader"
            else "it needs fundamentals data"
        )
        raise HTTPException(status_code=404, detail=f"{ticker} is not rated ({style}): {need}")
    return rec


@router.get("/track-record", response_model=TrackRecordOut)
async def track_record(
    session: AsyncSession = Depends(get_session),
    style: InvestingStyle = Depends(user_style),
) -> TrackRecordOut:
    """How past ratings (your investing style) did: backtest and live record."""
    backtest = load_backtest(style)
    return TrackRecordOut(
        style=style,
        horizon=HORIZON[style][0],
        backtest=backtest,
        live=await live_record(session, style),
    )


@router.get("/stocks/{ticker}/valuation", response_model=ValuationOut)
async def stock_valuation(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
) -> ValuationOut:
    """Where the current PBV/RoE sit within the stock's own history."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")
    return await valuation(session, ticker)


@router.get("/stocks/{ticker}/dividends", response_model=DividendSummary)
async def stock_dividends(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
) -> DividendSummary:
    """Dividend history + trailing yield for one ticker."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    rows = await list_dividends(session, ticker)
    dps = round((await trailing_dps(session, [ticker])).get(ticker, 0.0), 2)
    price = (await latest_daily(session, [ticker])).get(ticker, {}).get("close")
    yield_pct = round(dps / price * 100, 2) if dps and price else None
    return DividendSummary(
        ticker=ticker,
        trailing_dps=dps,
        yield_percent=yield_pct,
        history=[DividendOut.model_validate(r) for r in rows],
    )


@router.get("/stocks/{ticker}/company", response_model=CompanyOut)
async def stock_company(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
) -> CompanyOut:
    """Company profile + board/management (fetched on demand, cached)."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")

    async def load() -> StockProfile | None:
        return (
            await session.execute(
                select(StockProfile).where(StockProfile.ticker == ticker)
            )
        ).scalar_one_or_none()

    profile = await load()
    if profile is None or not profile.description:
        # Populate from the provider on first view (best-effort, governed).
        await sync_ticker(ticker)
        # sync_ticker commits in its own session; end ours + drop the cached
        # instance so the re-read sees the fresh row.
        await session.commit()
        session.expire_all()
        profile = await load()

    officers: list[OfficerOut] = []
    if profile and profile.officers:
        officers = [OfficerOut.model_validate(o) for o in profile.officers]

    return CompanyOut(
        ticker=stock.ticker,
        name=stock.name,
        sector=profile.sector if profile else None,
        industry=profile.industry if profile else None,
        description=profile.description if profile else None,
        employees=profile.employees if profile else None,
        website=profile.website if profile else None,
        country=profile.country if profile else None,
        city=profile.city if profile else None,
        address=profile.address if profile else None,
        phone=profile.phone if profile else None,
        officers=officers,
    )


@router.get("/catalog", response_model=CatalogPage)
async def catalog(
    q: str | None = Query(None, max_length=40),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> CatalogPage:
    """Browse the full IDX catalog (search by ticker or name), one page at a time."""
    term = (q or "").strip()
    match = (
        or_(Stock.ticker.ilike(f"%{term}%"), Stock.name.ilike(f"%{term}%")) if term else None
    )
    count_stmt = select(func.count()).select_from(Stock)
    stmt = select(Stock)
    if match is not None:
        count_stmt = count_stmt.where(match)
        stmt = stmt.where(match)
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Stock.ticker).limit(limit).offset(offset)
    stocks = (await session.execute(stmt)).scalars().all()

    tickers = [s.ticker for s in stocks]
    price_map = await latest_daily(session, tickers)
    index_map = await indices_map(session, tickers)

    rows: list[CatalogRow] = []
    for s in stocks:
        info = price_map.get(s.ticker, {})
        last = info.get("close")
        prev = info.get("prev_close")
        chg = (
            round((last - prev) / prev * 100, 2)
            if last is not None and prev not in (None, 0)
            else None
        )
        rows.append(
            CatalogRow(
                ticker=s.ticker,
                name=s.name,
                board=s.listing_board,
                tracked=s.tracked,
                indices=index_map.get(s.ticker, []),
                last_price=last,
                change_percent=chg,
            )
        )
    return CatalogPage(items=rows, total=total, limit=limit, offset=offset)


@router.post(
    "/stocks/{ticker}/track", response_model=CatalogRow, dependencies=[Depends(require_admin)]
)
async def track_symbol(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
) -> CatalogRow:
    """Add a symbol to the high-frequency (intraday) sync set."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")
    stock.tracked = True
    await session.commit()
    return CatalogRow(ticker=stock.ticker, name=stock.name, tracked=True)


@router.delete(
    "/stocks/{ticker}/track", response_model=CatalogRow, dependencies=[Depends(require_admin)]
)
async def untrack_symbol(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
) -> CatalogRow:
    """Remove a symbol from the high-frequency sync set."""
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {ticker}")
    stock.tracked = False
    await session.commit()
    return CatalogRow(ticker=stock.ticker, name=stock.name, tracked=False)
