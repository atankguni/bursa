"""
Evaluate the recommendation engine against what prices actually did next.

Runs the app's own factor functions / `score_universe` at past as-of dates using
only data that existed then (point-in-time), and reports forward returns per
rating plus the rank IC (Spearman correlation of score vs forward return).
Read-only: it only runs SELECTs, on whichever database DATABASE_URL points at.

Styles: `investor` (monthly as-of dates, 1m/3m horizons) and `trader`
(weekly as-of dates, 1w/2w/4w horizons; price factors only).

Look-ahead guards: prices are truncated at the as-of date; fundamentals are
limited to fiscal years already published (annual reports land ~March/April);
provider profile metrics (current trailing PE / growth) are not used, only the
sector. Caveats: survivorship (current listings), overlapping 3m windows, and
the history is only as long as the stored daily bars (DAILY_HISTORY_YEARS) and
yearly fundamentals (~4-5 fiscal years).

Besides the overall tables, results are split by calendar year (different
market conditions: a factor that only worked in one year is luck, not signal)
and by sector, for the main horizon on liquid stocks.

Usage (inside the backend environment):
    python scripts/evaluate_signals.py [--style investor|trader] [--db data/bursa.db | --url URL]
                                       [--write-summary]

`--write-summary` also stores the main-horizon result per rating in
services/backtest_summary.json: the track record the app shows next to ratings.
Re-run it (for both styles) after changing the model, and commit the file.

`--db` is a SQLite file; `--url` any SQLAlchemy async URL. Default: DATABASE_URL.

Rule of thumb for the IC: ~0 = noise, > 0.05 useful, > 0.10 good.
"""

import argparse
import asyncio
import bisect
import collections
import json
import statistics as st
import sys
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from config import settings  # noqa: E402
from models import Fundamental, StockPrice, StockProfile  # noqa: E402
from schemas import InvestingStyle  # noqa: E402
from services.recommendation import (  # noqa: E402
    CATEGORY_ORDER,
    TRADER_CATEGORY_ORDER,
    raw_factors,
    score_universe,
    trader_factors,
)
from services.track_record import HORIZON, SUMMARY_FILE, beat_rates  # noqa: E402

RATINGS = ["Strong Buy", "Buy", "Hold", "Reduce", "Avoid"]
CATEGORIES: dict[InvestingStyle, list[str]] = {
    "investor": CATEGORY_ORDER,
    "trader": TRADER_CATEGORY_ORDER,
}
# Forward-return horizons in trading days.
HORIZONS: dict[InvestingStyle, dict[str, int]] = {
    "investor": {"1m": 21, "3m": 63},
    "trader": {"1w": 5, "2w": 10, "4w": 20},
}


class Bar(TypedDict):
    day: str
    close: float
    volume: float


class Sample(TypedDict):
    asof: str
    ticker: str
    sector: str
    score: float
    rating: str
    liquidity: float
    categories: dict[str, float | None]
    forward: dict[str, float | None]


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load(url: str) -> tuple[dict[str, list[Bar]], dict[str, list[Any]], dict[str, str | None]]:
    return asyncio.run(_load(url))


async def _load(
    url: str,
) -> tuple[dict[str, list[Bar]], dict[str, list[Any]], dict[str, str | None]]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as con:
            prices: dict[str, list[Bar]] = collections.defaultdict(list)
            for ticker, ts, close, volume in await con.execute(
                select(StockPrice.ticker, StockPrice.timestamp, StockPrice.close,
                       StockPrice.volume)
                .where(StockPrice.interval == "1d")
                .order_by(StockPrice.ticker, StockPrice.timestamp)
            ):
                prices[ticker].append(
                    Bar(day=ts.date().isoformat(), close=close, volume=volume or 0)
                )

            # Duck-typed stand-ins for models.Fundamental (raw_factors only reads attributes).
            funds: dict[str, list[Any]] = collections.defaultdict(list)
            for row in await con.execute(
                select(Fundamental.ticker, Fundamental.fiscal_year, Fundamental.total_shares,
                       Fundamental.revenue, Fundamental.net_income, Fundamental.total_assets,
                       Fundamental.total_liabilities, Fundamental.equity)
                .order_by(Fundamental.ticker, Fundamental.fiscal_year)
            ):
                funds[row[0]].append(
                    SimpleNamespace(
                        fiscal_year=row[1], total_shares=row[2], revenue=row[3],
                        net_income=row[4], total_assets=row[5], total_liabilities=row[6],
                        equity=row[7],
                    )
                )
            sectors: dict[str, str | None] = dict(
                (await con.execute(select(StockProfile.ticker, StockProfile.sector))).all()
            )
    finally:
        await engine.dispose()
    return prices, funds, sectors


def sector_only_profile(sector: str | None) -> Any:
    """A profile carrying just the sector, so no current (look-ahead) metrics leak in."""
    if sector is None:
        return None
    return SimpleNamespace(
        sector=sector, trailing_pe=None, profit_margin=None,
        revenue_growth=None, earnings_growth=None,
    )


# --------------------------------------------------------------------------- #
# Statistics helpers
# --------------------------------------------------------------------------- #
def _ranks(xs: Sequence[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2  # average rank for ties
        i = j + 1
    return out


def spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    if len(a) < 10:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else None


def median_traded_value(bars: list[Bar], upto: int, days: int = 20) -> float:
    window = bars[max(0, upto - days + 1) : upto + 1]
    return st.median(b["close"] * b["volume"] for b in window) if window else 0.0


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #
def monthly_asofs(calendar: list[str]) -> list[str]:
    """Trading days nearest the 15th of each month with enough history and future."""
    earliest = calendar[min(len(calendar) - 1, 63)]  # momentum needs ~3 months
    latest = calendar[max(0, len(calendar) - 1 - HORIZONS["investor"]["1m"])]
    out: list[str] = []
    for day in calendar:
        if earliest <= day <= latest and day[8:] >= "15" and (not out or out[-1][:7] != day[:7]):
            out.append(day)
    return out


def weekly_asofs(calendar: list[str]) -> list[str]:
    """Every 5th trading day with enough history and at least a week of future."""
    return calendar[63 : max(63, len(calendar) - HORIZONS["trader"]["1w"]) : 5]


# Bars the factor functions look at (momentum uses one trading year).
LOOKBACK = 260


def backtest(
    prices: dict[str, list[Bar]],
    funds: dict[str, list[Any]],
    sectors: dict[str, str | None],
    asofs: list[str],
    calendar: list[str],
    style: InvestingStyle = "investor",
) -> list[Sample]:
    samples: list[Sample] = []
    days = {t: [b["day"] for b in bars] for t, bars in prices.items()}
    all_closes = {t: [b["close"] for b in bars] for t, bars in prices.items()}
    for asof in asofs:
        stale_before = calendar[max(0, calendar.index(asof) - 5)]
        year, month = int(asof[:4]), int(asof[5:7])
        published = year - 1 if month >= 4 else year - 2
        raw, liquidity, forward = {}, {}, {}
        for ticker, bars in prices.items():
            idx = bisect.bisect_right(days[ticker], asof) - 1
            if idx < 63 or bars[idx]["day"] < stale_before:
                continue  # too little history, or not trading around the as-of date
            closes = all_closes[ticker][max(0, idx + 1 - LOOKBACK) : idx + 1]
            if style == "trader":
                raw[ticker] = trader_factors(closes)
            else:
                visible = [f for f in funds.get(ticker, []) if f.fiscal_year <= published]
                raw[ticker] = raw_factors(
                    closes, visible, sector_only_profile(sectors.get(ticker)), closes[-1]
                )
            liquidity[ticker] = median_traded_value(bars, idx)
            entry = bars[idx]["close"]
            forward[ticker] = {
                name: (bars[idx + h]["close"] / entry - 1 if idx + h < len(bars) else None)
                for name, h in HORIZONS[style].items()
            }
        for ticker, rec in score_universe(raw, liquidity, style).items():
            samples.append(
                Sample(
                    asof=asof, ticker=ticker, sector=sectors.get(ticker) or "Unknown",
                    score=rec.score, rating=rec.rating,
                    liquidity=liquidity[ticker],
                    categories={c.name: c.score for c in rec.categories},
                    forward=forward[ticker],
                )
            )
    return samples


def report(
    samples: list[Sample], asofs: list[str], horizon: str, title: str,
    keep: Callable[[Sample], bool], categories: list[str],
) -> None:
    sel = [s for s in samples if s["forward"][horizon] is not None and keep(s)]
    if not sel:
        return

    def fwd(s: Sample) -> float:
        value = s["forward"][horizon]
        assert value is not None
        return value

    median_by_date = {d: st.median([fwd(s) for s in sel if s["asof"] == d] or [0.0]) for d in asofs}
    print(f"\n-- {title}, forward {horizon} (n={len(sel)}) --")
    print(f"{'rating':11} {'n':>5} {'mean':>7} {'median':>7} {'beat-median':>12}")
    for rating in RATINGS:
        group = [s for s in sel if s["rating"] == rating]
        if len(group) < 5:
            continue
        beat = sum(fwd(s) > median_by_date[s["asof"]] for s in group) / len(group) * 100
        print(
            f"{rating:11} {len(group):5} {st.mean(map(fwd, group)) * 100:6.1f}% "
            f"{st.median(map(fwd, group)) * 100:6.1f}% {beat:11.0f}%"
        )

    def ic_series(value: Callable[[Sample], float | None]) -> list[float]:
        ics: list[float] = []
        for d in asofs:
            pairs = [(v, fwd(s)) for s in sel if s["asof"] == d and (v := value(s)) is not None]
            ic = spearman([p[0] for p in pairs], [p[1] for p in pairs])
            if ic is not None:
                ics.append(ic)
        return ics

    ics = ic_series(lambda s: s["score"])
    if ics:
        spread = st.pstdev(ics) or 1e-9
        # Per-date values only while they fit on a line; BY YEAR summarises long runs.
        per_date = f"  per date={' '.join(f'{x:+.2f}' for x in ics)}" if len(ics) <= 24 else ""
        print(
            f"rank IC (score): mean={st.mean(ics):+.3f}  mean/sd={st.mean(ics) / spread:+.2f}  "
            f"positive on {sum(x > 0 for x in ics)}/{len(ics)} dates{per_date}"
        )
    for cat in categories:
        cics = ic_series(lambda s, c=cat: s["categories"].get(c))
        if cics:
            print(f"   IC {cat:9} mean={st.mean(cics):+.3f}")


def _ic_mean(group: list[Sample], horizon: str) -> tuple[float | None, int]:
    """Mean per-date rank IC of the score within `group`, and how many dates had one."""
    by_date: dict[str, list[Sample]] = collections.defaultdict(list)
    for s in group:
        by_date[s["asof"]].append(s)
    ics = [
        ic for d in by_date.values()
        if (ic := spearman([s["score"] for s in d],
                           [s["forward"][horizon] or 0.0 for s in d])) is not None
    ]
    return (st.mean(ics) if ics else None), len(ics)


def report_by(
    samples: list[Sample], horizon: str, title: str, keep: Callable[[Sample], bool],
    group_of: Callable[[Sample], str], min_n: int = 30,
) -> None:
    """One line per group (year, sector, ...): market move, rank IC and how often
    top / bottom ratings beat that date's median stock."""
    sel = [s for s in samples if s["forward"][horizon] is not None and keep(s)]
    if not sel:
        return
    median_by_date = {
        d: st.median([s["forward"][horizon] or 0.0 for s in sel if s["asof"] == d])
        for d in {s["asof"] for s in sel}
    }
    groups: dict[str, list[Sample]] = collections.defaultdict(list)
    for s in sel:
        groups[group_of(s)].append(s)

    def beat(group: list[Sample]) -> str:
        if len(group) < 5:
            return "     —"
        wins = sum((s["forward"][horizon] or 0.0) > median_by_date[s["asof"]] for s in group)
        return f"{wins / len(group) * 100:5.0f}%"

    print(f"\n-- {title}, forward {horizon} --")
    print(f"{'group':24} {'n':>6} {'market':>7} {'IC':>6} {'dates':>5} "
          f"{'Buy+ beat':>9} {'Avoid beat':>10}")
    for name in sorted(groups):
        group = groups[name]
        if len(group) < min_n:
            continue
        ic, n_dates = _ic_mean(group, horizon)
        market = st.median(s["forward"][horizon] or 0.0 for s in group) * 100
        top = [s for s in group if s["rating"] in ("Strong Buy", "Buy")]
        bottom = [s for s in group if s["rating"] == "Avoid"]
        print(f"{name[:24]:24} {len(group):6} {market:6.1f}% "
              f"{'     —' if ic is None else f'{ic:+.3f}':>6} {n_dates:5} "
              f"{beat(top):>9} {beat(bottom):>10}")


def write_summary(
    samples: list[Sample], style: InvestingStyle, keep: Callable[[Sample], bool], universe: str
) -> None:
    """Store the main-horizon track record for the app (services/track_record)."""
    horizon = HORIZON[style][0]
    sel = [s for s in samples if s["forward"][horizon] is not None and keep(s)]
    by_year: dict[str, list[Sample]] = collections.defaultdict(list)
    for s in sel:
        by_year[s["asof"][:4]].append(s)
    ic, _ = _ic_mean(sel, horizon)
    years = {y: round(v, 3) for y, g in sorted(by_year.items())
             if (v := _ic_mean(g, horizon)[0]) is not None}
    dates = sorted({s["asof"] for s in sel})
    entry = {
        "start": dates[0], "end": dates[-1], "universe": universe,
        "ic": round(ic or 0.0, 3), "years": years,
        "ratings": beat_rates((s["asof"], s["rating"], s["forward"][horizon] or 0.0) for s in sel),
        "generated": date.today().isoformat(),
    }
    try:
        data = json.loads(SUMMARY_FILE.read_text())
    except (OSError, ValueError):
        data = {}
    data[style] = entry
    SUMMARY_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\nWrote the {style} track record to {SUMMARY_FILE}")


def snapshot(
    prices: dict[str, list[Bar]],
    funds: dict[str, list[Any]],
    sectors: dict[str, str | None],
    style: InvestingStyle,
) -> None:
    """Ratings as of the latest bar (sector-only profile, like the backtest)."""
    raw, liquidity = {}, {}
    for ticker, bars in prices.items():
        closes = [b["close"] for b in bars]
        raw[ticker] = (
            trader_factors(closes)
            if style == "trader"
            else raw_factors(
                closes, funds.get(ticker, []), sector_only_profile(sectors.get(ticker)), closes[-1]
            )
        )
        liquidity[ticker] = median_traded_value(bars, len(bars) - 1)
    recs = score_universe(raw, liquidity, style)
    counts = collections.Counter(r.rating for r in recs.values())
    print(f"=== {style.upper()} SNAPSHOT: {len(recs)} of {len(prices)} stocks rated ===")
    print("  ".join(f"{r}={counts.get(r, 0)}" for r in RATINGS))
    capped = sum(any("Thinly traded" in x for x in r.reasons) for r in recs.values())
    print(f"capped at Hold for thin trading: {capped}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--db", help="SQLite database file")
    source.add_argument("--url", help="SQLAlchemy async URL (default: DATABASE_URL)")
    parser.add_argument("--style", choices=list(HORIZONS), default="investor")
    parser.add_argument("--write-summary", action="store_true",
                        help="store the main-horizon result for the app's track record")
    args = parser.parse_args()
    style: InvestingStyle = args.style

    url = args.url or (f"sqlite+aiosqlite:///{args.db}" if args.db else settings.database_url)
    prices, funds, sectors = load(url)
    if not prices:
        sys.exit("No daily prices in the database.")
    # Only days most of the universe covers: a few stocks store their full
    # history (chart "5Y"/"Max"), which must not drag as-of dates back decades.
    day_counts = collections.Counter(b["day"] for bars in prices.values() for b in bars)
    peak = max(day_counts.values())
    calendar = sorted(d for d, n in day_counts.items() if n >= peak * 0.5)
    asofs = weekly_asofs(calendar) if style == "trader" else monthly_asofs(calendar)

    snapshot(prices, funds, sectors, style)
    samples = backtest(prices, funds, sectors, asofs, calendar, style)
    print(f"\n=== BACKTEST {asofs[0]} -> {asofs[-1]} ({len(samples)} rated stock-dates) ===")

    floor = settings.recommendation_min_traded_value

    def liquid(s: Sample) -> bool:
        return s["liquidity"] >= floor

    for horizon in HORIZONS[style]:
        report(samples, asofs, horizon, "ALL rated", lambda s: True, CATEGORIES[style])
        if style == "investor":  # trader only rates liquid stocks already
            report(
                samples, asofs, horizon, f"LIQUID (>= Rp {floor / 1e9:g}bn/day)",
                liquid, CATEGORIES[style],
            )

    # Robustness on the main horizon: does it hold in every year and sector?
    main = list(HORIZONS[style])[-1]
    report_by(samples, main, "BY YEAR (liquid)", liquid, lambda s: s["asof"][:4])
    report_by(samples, main, "BY SECTOR (liquid; IC within the sector)", liquid,
              lambda s: s["sector"])
    if args.write_summary:
        # Investor ratings of illiquid stocks are capped, so judge liquid ones only.
        write_summary(
            samples, style, liquid if style == "investor" else (lambda s: True),
            f"liquid stocks (>= Rp {floor / 1e9:g}bn traded a day)",
        )


if __name__ == "__main__":
    main()
