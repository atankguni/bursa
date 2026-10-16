"""
services/portfolio_risk.py
--------------------------
Portfolio risk: concentration, sector exposure, beta vs IHSG, a simple stress
test, and max drawdown of the time-weighted return. Percentages and ratios
only (no amounts), so the view is safe in hide-values mode.
"""

from collections.abc import Sequence
from datetime import date
from statistics import fmean
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import IndexBar, IndexQuote, StockPrice, StockProfile
from services.portfolio import build_portfolio, equity_curve

STRESS_DROP_PCT = -10.0  # "if IHSG falls 10%"
MAX_STOCK_WEIGHT = 25.0  # % of portfolio before warning
MAX_SECTOR_WEIGHT = 40.0
BETA_WINDOW = 250  # ~1 trading year of daily returns


class HoldingRisk(TypedDict):
    ticker: str
    weight: float  # % of market value
    sector: str
    beta: float | None


class SectorWeight(TypedDict):
    sector: str
    weight: float


class PortfolioRisk(TypedDict):
    holdings: list[HoldingRisk]
    sectors: list[SectorWeight]
    effective_holdings: float | None  # 1 / sum(w^2)
    top_weight: float | None
    top3_weight: float | None
    beta: float | None
    stress_ihsg_pct: float
    stress_portfolio_pct: float | None
    last_day_portfolio_pct: float | None
    last_day_ihsg_pct: float | None
    max_drawdown_pct: float | None
    warnings: list[str]


def beta(
    stock: Sequence[tuple[date, float]], market: Sequence[tuple[date, float]]
) -> float | None:
    """Beta of daily returns on the dates both series share (None if too few)."""
    m_close = dict(market)
    s_close = dict(stock)
    days = sorted(set(s_close) & set(m_close))[-(BETA_WINDOW + 1):]
    rs, rm = [], []
    for prev, cur in zip(days, days[1:], strict=False):
        if s_close[prev] and m_close[prev]:
            rs.append(s_close[cur] / s_close[prev] - 1)
            rm.append(m_close[cur] / m_close[prev] - 1)
    if len(rs) < 40:
        return None
    ms, mm = fmean(rs), fmean(rm)
    var = sum((x - mm) ** 2 for x in rm)
    if var == 0:
        return None
    cov = sum((a - ms) * (b - mm) for a, b in zip(rs, rm, strict=True))
    return cov / var


def max_drawdown(growth_pct: list[float]) -> float | None:
    """Worst peak-to-trough fall (%) of a cumulative-return series."""
    if not growth_pct:
        return None
    peak, worst = 1.0, 0.0
    for pct in growth_pct:
        level = 1 + pct / 100
        peak = max(peak, level)
        worst = min(worst, level / peak - 1)
    return round(worst * 100, 2)


async def portfolio_risk(session: AsyncSession) -> PortfolioRisk:
    totals, holdings = await build_portfolio(session)
    tickers = [h["ticker"] for h in holdings]

    sectors = dict(
        (await session.execute(
            select(StockProfile.ticker, StockProfile.sector).where(StockProfile.ticker.in_(tickers))
        )).all()
    )
    market = [
        (d, c) for d, c in (await session.execute(
            select(IndexBar.day, IndexBar.close).where(IndexBar.code == "COMPOSITE")
        )).all()
    ]
    prices: dict[str, list[tuple[date, float]]] = {t: [] for t in tickers}
    for t, ts, close in (await session.execute(
        select(StockPrice.ticker, StockPrice.timestamp, StockPrice.close)
        .where(StockPrice.interval == "1d", StockPrice.ticker.in_(tickers))
    )).all():
        prices[t].append((ts.date(), close))

    rows: list[HoldingRisk] = [
        {
            "ticker": h["ticker"],
            "weight": h["weight"] or 0.0,
            "sector": sectors.get(h["ticker"]) or "Unknown",
            "beta": (round(b, 2) if (b := beta(prices[h["ticker"]], market)) is not None else None),
        }
        for h in holdings
    ]
    weights = [r["weight"] / 100 for r in rows]
    by_sector: dict[str, float] = {}
    for r in rows:
        by_sector[r["sector"]] = by_sector.get(r["sector"], 0.0) + r["weight"]
    sector_rows: list[SectorWeight] = sorted(
        ({"sector": s, "weight": round(w, 2)} for s, w in by_sector.items()),
        key=lambda x: -x["weight"],
    )

    with_beta = [(r["weight"], r["beta"]) for r in rows if r["beta"] is not None]
    covered = sum(w for w, _ in with_beta)
    port_beta = (
        round(sum(w * b for w, b in with_beta) / covered, 2) if covered > 0 else None
    )
    ihsg = await session.get(IndexQuote, "COMPOSITE")
    ihsg_day = (
        round((ihsg.last / ihsg.previous_close - 1) * 100, 2)
        if ihsg and ihsg.previous_close else None
    )
    curve = await equity_curve(session)
    ranked = sorted((r["weight"] for r in rows), reverse=True)

    warnings: list[str] = []
    for r in rows:
        if r["weight"] > MAX_STOCK_WEIGHT:
            warnings.append(
                f"{r['ticker'].removesuffix('.JK')} is {r['weight']:.0f}% of your portfolio "
                f"(above {MAX_STOCK_WEIGHT:.0f}%)"
            )
    for s in sector_rows:
        if s["weight"] > MAX_SECTOR_WEIGHT and len(rows) > 1:
            warnings.append(
                f"{s['sector']} is {s['weight']:.0f}% of your portfolio "
                f"(above {MAX_SECTOR_WEIGHT:.0f}%)"
            )
    if port_beta is not None and port_beta > 1.2:
        warnings.append(f"Beta {port_beta}: your portfolio swings more than the market")

    return {
        "holdings": rows,
        "sectors": sector_rows,
        "effective_holdings": (
            round(1 / sum(w * w for w in weights), 1) if any(weights) else None
        ),
        "top_weight": ranked[0] if ranked else None,
        "top3_weight": round(sum(ranked[:3]), 2) if ranked else None,
        "beta": port_beta,
        "stress_ihsg_pct": STRESS_DROP_PCT,
        "stress_portfolio_pct": (
            round(port_beta * STRESS_DROP_PCT, 1) if port_beta is not None else None
        ),
        "last_day_portfolio_pct": totals["day_change_pct"],
        "last_day_ihsg_pct": ihsg_day,
        "max_drawdown_pct": max_drawdown(
            [p["return_pct"] for p in curve if p["return_pct"] is not None]
        ),
        "warnings": warnings,
    }
