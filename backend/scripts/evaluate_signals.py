"""
Evaluate the recommendation engine against what prices actually did next.

Runs the app's own `raw_factors` / `score_universe` at monthly as-of dates using
only data that existed then (point-in-time), and reports forward returns per
rating plus the rank IC (Spearman correlation of score vs forward return).
Read-only: opens the SQLite file immutably.

Look-ahead guards: prices are truncated at the as-of date; fundamentals are
limited to fiscal years already published (annual reports land ~March/April);
provider profile metrics (current trailing PE / growth) are not used, only the
sector. Caveats: survivorship (current listings), overlapping 3m windows, and
the history is only as long as the stored daily bars (~1y by default).

Usage (inside the backend environment):
    python scripts/evaluate_signals.py [--db data/bursa.db]

Rule of thumb for the IC: ~0 = noise, > 0.05 useful, > 0.10 good.
"""

import argparse
import collections
import sqlite3
import statistics as st
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings  # noqa: E402
from services.recommendation import raw_factors, score_universe  # noqa: E402

RATINGS = ["Strong Buy", "Buy", "Hold", "Reduce", "Avoid"]
CATEGORIES = ["Quality", "Valuation", "Growth", "Momentum", "Health"]
HORIZONS = {"1m": 21, "3m": 63}


class Bar(TypedDict):
    day: str
    close: float
    volume: float


class Sample(TypedDict):
    asof: str
    ticker: str
    score: float
    rating: str
    liquidity: float
    categories: dict[str, float | None]
    forward: dict[str, float | None]


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load(db: str) -> tuple[dict[str, list[Bar]], dict[str, list[Any]], dict[str, str | None]]:
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    prices: dict[str, list[Bar]] = collections.defaultdict(list)
    for ticker, ts, close, volume in con.execute(
        "select ticker, timestamp, close, volume from stock_prices "
        "where interval='1d' order by ticker, timestamp"
    ):
        prices[ticker].append(Bar(day=ts[:10], close=close, volume=volume or 0))

    # Duck-typed stand-ins for models.Fundamental (raw_factors only reads attributes).
    funds: dict[str, list[Any]] = collections.defaultdict(list)
    for row in con.execute(
        "select ticker, fiscal_year, total_shares, revenue, net_income, total_assets, "
        "total_liabilities, equity from fundamentals order by ticker, fiscal_year"
    ):
        funds[row[0]].append(
            SimpleNamespace(
                fiscal_year=row[1], total_shares=row[2], revenue=row[3],
                net_income=row[4], total_assets=row[5], total_liabilities=row[6],
                equity=row[7],
            )
        )
    sectors = dict(con.execute("select ticker, sector from stock_profiles"))
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
    latest = calendar[max(0, len(calendar) - 1 - HORIZONS["1m"])]
    out: list[str] = []
    for day in calendar:
        if earliest <= day <= latest and day[8:] >= "15" and (not out or out[-1][:7] != day[:7]):
            out.append(day)
    return out


def backtest(
    prices: dict[str, list[Bar]],
    funds: dict[str, list[Any]],
    sectors: dict[str, str | None],
    asofs: list[str],
    calendar: list[str],
) -> list[Sample]:
    samples: list[Sample] = []
    for asof in asofs:
        stale_before = calendar[max(0, calendar.index(asof) - 5)]
        year, month = int(asof[:4]), int(asof[5:7])
        published = year - 1 if month >= 4 else year - 2
        raw, liquidity, forward = {}, {}, {}
        for ticker, bars in prices.items():
            idx = next((i for i in range(len(bars) - 1, -1, -1) if bars[i]["day"] <= asof), None)
            if idx is None or idx < 63 or bars[idx]["day"] < stale_before:
                continue  # too little history, or not trading around the as-of date
            visible = [f for f in funds.get(ticker, []) if f.fiscal_year <= published]
            raw[ticker] = raw_factors(
                [b["close"] for b in bars[: idx + 1]],
                visible,
                sector_only_profile(sectors.get(ticker)),
                bars[idx]["close"],
            )
            liquidity[ticker] = median_traded_value(bars, idx)
            entry = bars[idx]["close"]
            forward[ticker] = {
                name: (bars[idx + h]["close"] / entry - 1 if idx + h < len(bars) else None)
                for name, h in HORIZONS.items()
            }
        for ticker, rec in score_universe(raw, liquidity).items():
            samples.append(
                Sample(
                    asof=asof, ticker=ticker, score=rec.score, rating=rec.rating,
                    liquidity=liquidity[ticker],
                    categories={c.name: c.score for c in rec.categories},
                    forward=forward[ticker],
                )
            )
    return samples


def report(
    samples: list[Sample], asofs: list[str], horizon: str, title: str,
    keep: Callable[[Sample], bool],
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
        print(
            f"rank IC (score): mean={st.mean(ics):+.3f}  mean/sd={st.mean(ics) / spread:+.2f}  "
            f"per date={' '.join(f'{x:+.2f}' for x in ics)}"
        )
    for cat in CATEGORIES:
        cics = ic_series(lambda s, c=cat: s["categories"].get(c))
        if cics:
            print(f"   IC {cat:9} mean={st.mean(cics):+.3f}")


def snapshot(
    prices: dict[str, list[Bar]], funds: dict[str, list[Any]], sectors: dict[str, str | None]
) -> None:
    """Ratings as of the latest bar (sector-only profile, like the backtest)."""
    raw, liquidity = {}, {}
    for ticker, bars in prices.items():
        raw[ticker] = raw_factors(
            [b["close"] for b in bars], funds.get(ticker, []),
            sector_only_profile(sectors.get(ticker)), bars[-1]["close"],
        )
        liquidity[ticker] = median_traded_value(bars, len(bars) - 1)
    recs = score_universe(raw, liquidity)
    counts = collections.Counter(r.rating for r in recs.values())
    print(f"=== SNAPSHOT: {len(recs)} of {len(prices)} stocks rated ===")
    print("  ".join(f"{r}={counts.get(r, 0)}" for r in RATINGS))
    capped = sum(any("Thinly traded" in x for x in r.reasons) for r in recs.values())
    print(f"capped at Hold for thin trading: {capped}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--db", default=str(Path(__file__).resolve().parents[1] / "data/bursa.db"))
    args = parser.parse_args()

    prices, funds, sectors = load(args.db)
    if not prices:
        sys.exit("No daily prices in the database.")
    calendar = sorted({b["day"] for bars in prices.values() for b in bars})
    asofs = monthly_asofs(calendar)

    snapshot(prices, funds, sectors)
    samples = backtest(prices, funds, sectors, asofs, calendar)
    print(f"\n=== BACKTEST {asofs[0]} -> {asofs[-1]} ({len(samples)} rated stock-dates) ===")

    floor = settings.recommendation_min_traded_value
    for horizon in HORIZONS:
        report(samples, asofs, horizon, "ALL rated", lambda s: True)
        report(
            samples, asofs, horizon, f"LIQUID (>= Rp {floor / 1e9:g}bn/day)",
            lambda s: s["liquidity"] >= floor,
        )


if __name__ == "__main__":
    main()
