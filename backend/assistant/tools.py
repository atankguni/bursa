"""
assistant/tools.py
------------------
Read-only tools the assistant can call. Each wraps an existing service and reads
only stored data (never the market-data provider), so a question can't trigger
Yahoo traffic or change anything. Personal tools (watchlist, portfolio) are only
offered when `assistant_personal_data` is enabled.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant.providers import ToolSpec
from market.metrics import derive_metrics
from market.models import DailyBar, Fundamental, Stock
from market.overview import overview
from market.prices import latest_daily
from portfolio.holdings import build_portfolio
from portfolio.models import Watchlist
from schemas import InvestingStyle, stock_code
from signals.recommendation import compute_universe_cached, rating_code, rating_label
from signals.schemas import RatingRecordOut, ScreenerRow
from signals.screener import build_rows, filter_rows
from signals.track_record import HORIZON, live_record, load_backtest


@dataclass(frozen=True)
class ToolContext:
    """What a tool may use: the DB session and who is asking (their style)."""

    session: AsyncSession
    user_id: int
    style: InvestingStyle


# Arguments are the model's JSON (untrusted, read with care); the result is any
# value `to_jsonable_python` can encode.
type Handler = Callable[[ToolContext, dict[str, Any]], Awaitable[object]]


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    handler: Handler
    personal: bool = False


def _ticker(raw: object) -> str:
    """Accept 'bbca', 'BBCA' or 'BBCA.JK' -> 'BBCA'."""
    return stock_code(str(raw or ""))


def _float(args: dict[str, Any], key: str) -> float | None:
    """Model-supplied numbers may arrive as strings ("1.5") or be absent."""
    try:
        return None if args.get(key) in (None, "") else float(args[key])
    except (TypeError, ValueError):
        return None


def _num(v: float | None, digits: int = 4) -> float | None:
    return None if v is None else round(v, digits)


def _row(r: ScreenerRow) -> dict[str, Any]:
    return {
        "ticker": r.ticker, "name": r.name, "sector": r.sector,
        "indices": r.indices, "price": r.price, "change_pct": r.change_percent,
        "pbv": r.pbv, "roe": r.roe, "signal_score": r.score,
        "rating": rating_label(r.rating) if r.rating else None,
        "conviction": r.strength,
        "special_monitoring": r.board == "Watchlist",
    }


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
async def search_stocks(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    q = str(args.get("query", "")).strip()
    if len(q) < 2:
        return {"error": "query must be at least 2 characters"}
    like = f"%{q}%"
    rows = (
        await session.execute(
            select(Stock.ticker, Stock.name)
            .where(or_(Stock.ticker.ilike(like), Stock.name.ilike(like)))
            .order_by(Stock.ticker)
            .limit(min(int(args.get("limit", 10)), 25))
        )
    ).all()
    return [{"ticker": t, "name": n} for t, n in rows]


async def get_stock(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    ticker = _ticker(args.get("ticker"))
    for r in await build_rows(session, ctx.style):
        if r.ticker == ticker:
            return _row(r)
    return {"error": f"{ticker} is not in the app's universe (try search_stocks)"}


async def screen_stocks(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    rows = filter_rows(
        await build_rows(session, ctx.style),
        min_score=_float(args, "min_score"),
        max_pbv=_float(args, "max_pbv"),
        min_roe=_float(args, "min_roe"),
        rating=rating_code(args.get("rating")),
        sector=args.get("sector") or None,
        buy_only=bool(args.get("buy_only", False)),
    )
    sort_by = args.get("sort_by", "signal_score")
    columns: dict[str, Callable[[ScreenerRow], float | None]] = {
        "signal_score": lambda r: r.score,
        "pbv": lambda r: r.pbv,
        "roe": lambda r: r.roe,
        "change_pct": lambda r: r.change_percent,
    }
    column = columns.get(sort_by, columns["signal_score"])
    descending = sort_by != "pbv"  # cheapest PBV first, otherwise highest first

    def order(r: ScreenerRow) -> tuple[bool, float]:
        value = column(r)
        return value is None, -(value or 0.0) if descending else (value or 0.0)

    rows.sort(key=order)
    limit = max(1, min(int(args.get("limit", 10)), 20))
    return {"matched": len(rows), "rows": [_row(r) for r in rows[:limit]]}


async def get_signal(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    ticker = _ticker(args.get("ticker"))
    style = ctx.style
    rec = (await compute_universe_cached(session, style)).get(ticker)
    if rec is None:
        need = ("too thinly traded or too little price history" if style == "trader"
                else "no fundamentals data yet")
        return {"ticker": ticker, "style": style, "rated": False, "why": need}
    return {"rated": True, **rec.model_dump(), "rating": rating_label(rec.rating)}


async def get_track_record(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    style = ctx.style

    def named(rows: list[RatingRecordOut]) -> list[dict[str, Any]]:
        return [{**r.model_dump(), "rating": rating_label(r.rating)} for r in rows]

    backtest = load_backtest(style)
    live = await live_record(session, style)
    return {
        "style": style,
        "horizon": HORIZON[style][0],
        "how_to_read": "beat = share of stocks with this rating that beat the median "
                       "stock over the horizon; 0.5 is a coin flip. ic = rank "
                       "correlation of score vs. later return (~0 noise, >0.05 useful).",
        "backtest": backtest and {**backtest.model_dump(), "ratings": named(backtest.ratings)},
        "live": {**live.model_dump(), "ratings": named(live.ratings)},
    }


async def get_fundamentals(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    ticker = _ticker(args.get("ticker"))
    funds = (
        await session.execute(
            select(Fundamental)
            .where(Fundamental.ticker == ticker)
            .order_by(Fundamental.fiscal_year)
        )
    ).scalars().all()
    if not funds:
        return {"ticker": ticker, "error": "no fundamentals stored for this stock"}
    price = (await latest_daily(session, [ticker])).get(ticker, {}).get("close")
    m = derive_metrics(price, funds[-1])
    return {
        "ticker": ticker,
        "currency": "IDR (converted if the company reports in another currency)",
        "latest": {"price": price, "market_cap": m.market_cap, "book_value": m.book_value,
                   "pbv": m.pbv, "roe": m.roe},
        "yearly": [
            {"year": f.fiscal_year, "revenue": f.revenue, "net_income": f.net_income,
             "total_assets": f.total_assets, "total_liabilities": f.total_liabilities,
             "equity": f.equity, "shares": f.total_shares}
            for f in funds
        ],
    }


async def get_price_history(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    ticker = _ticker(args.get("ticker"))
    days = max(5, min(int(args.get("days", 30)), 250))
    bars = (
        await session.execute(
            select(DailyBar.day, DailyBar.close, DailyBar.volume)
            .where(DailyBar.ticker == ticker)
            .order_by(DailyBar.day.desc())
            .limit(days)
        )
    ).all()[::-1]
    if not bars:
        return {"ticker": ticker, "error": "no price history stored"}
    closes = [b[1] for b in bars]
    step = max(1, len(bars) // 30)  # at most ~30 points back to the model
    return {
        "ticker": ticker, "days": len(bars),
        "first": {"date": bars[0][0].isoformat(), "close": closes[0]},
        "last": {"date": bars[-1][0].isoformat(), "close": closes[-1]},
        "return_pct": _num((closes[-1] / closes[0] - 1) * 100, 2) if closes[0] else None,
        "high": max(closes), "low": min(closes),
        "avg_volume": int(sum(b[2] for b in bars) / len(bars)),
        "closes": [{"date": b[0].isoformat(), "close": b[1]} for b in bars[::step]],
    }


async def market_overview(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    return await overview(session)


async def get_investing_style_tool(ctx: ToolContext, args: dict[str, Any]) -> object:
    style = ctx.style
    return {"style": style, "meaning": {
        "investor": "long-term; signals from fundamentals (quality, valuation, growth, health)",
        "trader": "swing, 1-4 weeks; signals from price behaviour "
                  "(stability, setup near the 20-day high)",
    }[style]}


async def get_watchlist(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    tickers = set((await session.execute(
        select(Watchlist.ticker).where(Watchlist.user_id == ctx.user_id)
    )).scalars().all())
    return [_row(r) for r in await build_rows(session, ctx.style) if r.ticker in tickers]


async def get_portfolio(ctx: ToolContext, args: dict[str, Any]) -> object:
    session = ctx.session
    totals, holdings = await build_portfolio(session, ctx.user_id)
    return {"totals": totals, "holdings": holdings}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_TICKER = {"type": "string", "description": "IDX code, e.g. BBCA"}

TOOLS: list[Tool] = [
    Tool(ToolSpec("search_stocks", "Find IDX stocks by code or company name.",
                  {"type": "object", "properties": {
                      "query": {"type": "string"}, "limit": {"type": "integer"}},
                   "required": ["query"]}), search_stocks),
    Tool(ToolSpec("get_stock", "Latest price, daily change, sector, PBV, RoE and the "
                  "signal rating for one stock.",
                  {"type": "object", "properties": {"ticker": _TICKER}, "required": ["ticker"]}),
         get_stock),
    Tool(ToolSpec("screen_stocks", "Filter and rank the stock universe. RoE is a fraction "
                  "(0.15 = 15%). Ratings: Very positive, Positive, Neutral, Negative, "
                  "Very negative.",
                  {"type": "object", "properties": {
                      "min_score": {"type": "number", "description": "signal score 0-100"},
                      "max_pbv": {"type": "number"},
                      "min_roe": {"type": "number"},
                      "rating": {"type": "string"},
                      "sector": {"type": "string", "description": "e.g. Financial Services"},
                      "buy_only": {"type": "boolean",
                                   "description": "Positive / Very positive only"},
                      "sort_by": {"type": "string",
                                  "enum": ["signal_score", "pbv", "roe", "change_pct"]},
                      "limit": {"type": "integer", "description": "max 20"}}}),
         screen_stocks),
    Tool(ToolSpec("get_signal", "Full signal breakdown for one stock: score, rating, "
                  "conviction, category scores, drivers, and which investing style "
                  "produced it.",
                  {"type": "object", "properties": {"ticker": _TICKER}, "required": ["ticker"]}),
         get_signal),
    Tool(ToolSpec("get_track_record", "How well this style's ratings worked: per "
                  "rating, how often stocks beat the median stock afterwards, in the "
                  "backtest and in the live record since recording started.",
                  {"type": "object", "properties": {}}), get_track_record),
    Tool(ToolSpec("get_fundamentals", "Yearly financials (IDR) and derived PBV/RoE.",
                  {"type": "object", "properties": {"ticker": _TICKER}, "required": ["ticker"]}),
         get_fundamentals),
    Tool(ToolSpec("get_price_history", "Daily closing prices over the last N trading days, "
                  "with return, high/low and average volume.",
                  {"type": "object", "properties": {
                      "ticker": _TICKER, "days": {"type": "integer", "description": "5-250"}},
                   "required": ["ticker"]}), get_price_history),
    Tool(ToolSpec("market_overview", "Market breadth (up/down/flat), top gainers and "
                  "losers, and average change by sector.",
                  {"type": "object", "properties": {}}), market_overview),
    Tool(ToolSpec("get_investing_style", "The user's investing style setting "
                  "(investor or trader), which decides how signals are scored.",
                  {"type": "object", "properties": {}}), get_investing_style_tool),
    Tool(ToolSpec("get_watchlist", "The user's watchlist with price and signal per stock.",
                  {"type": "object", "properties": {}}), get_watchlist, personal=True),
    Tool(ToolSpec("get_portfolio", "The user's holdings, invested amount, market value, "
                  "unrealized/realized P/L and allocation.",
                  {"type": "object", "properties": {}}), get_portfolio, personal=True),
]


def available_tools(include_personal: bool) -> dict[str, Tool]:
    return {t.spec.name: t for t in TOOLS if include_personal or not t.personal}
