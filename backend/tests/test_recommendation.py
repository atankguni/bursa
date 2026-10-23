"""Unit tests for the recommendation engine (pure functions, no DB/network)."""

from services.recommendation import percentile, raw_factors, score_universe


def _raw(**kw) -> dict:
    keys = [
        "roe", "net_margin", "pbv", "per", "revenue_yoy", "earnings_yoy",
        "ret_3m", "price_vs_sma50", "pos_52w", "der", "equity_ratio",
    ]
    return {k: kw.get(k) for k in keys}


def test_percentile_bounds_and_ordering():
    vals = [1.0, 2.0, 3.0, 4.0]
    assert percentile(vals, 1.0) < percentile(vals, 2.0) < percentile(vals, 4.0)
    assert percentile(vals, 4.0) > 80
    assert percentile([5.0], 5.0) == 50.0  # single value -> neutral


def test_ranking_and_ratings():
    raw = {
        "GOOD": _raw(
            roe=0.25, net_margin=0.30, pbv=1.0, per=8, revenue_yoy=0.20,
            earnings_yoy=0.25, ret_3m=0.15, price_vs_sma50=0.08, pos_52w=0.9,
            der=0.3, equity_ratio=0.7,
        ),
        "MID": _raw(
            roe=0.15, net_margin=0.15, pbv=2.0, per=15, revenue_yoy=0.08,
            earnings_yoy=0.10, ret_3m=0.03, price_vs_sma50=0.01, pos_52w=0.5,
            der=0.6, equity_ratio=0.5,
        ),
        "BAD": _raw(
            roe=0.03, net_margin=0.02, pbv=4.0, per=30, revenue_yoy=-0.05,
            earnings_yoy=-0.10, ret_3m=-0.10, price_vs_sma50=-0.05, pos_52w=0.1,
            der=1.5, equity_ratio=0.25,
        ),
    }
    rec = score_universe(raw)

    assert rec["GOOD"].score > rec["MID"].score > rec["BAD"].score
    assert rec["GOOD"].rating == "Buy"  # investor style has no Strong Buy
    assert rec["BAD"].rating in ("Reduce", "Avoid")
    assert rec["GOOD"].coverage == 1.0
    assert rec["GOOD"].disclaimer  # non-empty


def test_lower_is_better_for_valuation():
    # Identical except PBV: the cheaper stock must score higher on valuation.
    raw = {
        "CHEAP": _raw(pbv=1.0),
        "PRICEY": _raw(pbv=5.0),
    }
    rec = score_universe(raw)
    cheap_val = next(c for c in rec["CHEAP"].categories if c.name == "Valuation")
    pricey_val = next(c for c in rec["PRICEY"].categories if c.name == "Valuation")
    assert (cheap_val.score or 0) > (pricey_val.score or 0)


def test_sparse_data_lowers_coverage_and_strength():
    raw = {"THIN": _raw(roe=0.2)}  # only 1 of 11 factors
    rec = score_universe(raw)["THIN"]
    assert rec.coverage is not None and rec.coverage < 0.2
    assert rec.strength in ("Weak", "Moderate")


def test_raw_factors_from_fundamentals_and_prices():
    from models import Fundamental

    f = Fundamental(
        ticker="X", fiscal_year=2024, financial_currency="IDR",
        total_shares=1000.0, revenue=10_000.0, net_income=2_000.0,
        total_assets=9_000.0, total_liabilities=4_000.0, equity=5_000.0,
    )
    closes = [100.0] * 70 + [120.0]  # rising into the latest close
    raw = raw_factors(closes, [f], None, price=120.0)

    assert raw["roe"] == 2000 / 5000
    assert raw["net_margin"] == 0.2
    # market cap = 120 * 1000 = 120_000 ; book = 9000 - 4000 = 5000 -> PBV 24
    assert raw["pbv"] == 120_000 / 5000
    assert raw["per"] == 120.0 / (2000 / 1000)  # EPS 2 -> PER 60
    assert raw["ret_3m"] is not None and raw["pos_52w"] == 1.0


def _fund(**kw):
    from models import Fundamental

    base = {
        "ticker": "X", "fiscal_year": 2024, "financial_currency": "IDR",
        "total_shares": 1000.0, "revenue": 10_000.0, "net_income": 2_000.0,
        "total_assets": 9_000.0, "total_liabilities": 4_000.0, "equity": 5_000.0,
    }
    return Fundamental(**(base | kw))


def test_price_only_stocks_are_not_rated():
    # Momentum alone backtested as noise -> no rating without fundamentals.
    raw = {
        "FUND": _raw(roe=0.2, pbv=1.5, ret_3m=0.01),
        "MOMO": _raw(ret_3m=0.9, price_vs_sma50=0.5, pos_52w=1.0),
    }
    rec = score_universe(raw)
    assert "FUND" in rec
    assert "MOMO" not in rec


def test_thinly_traded_buy_is_capped_at_hold():
    good = {"roe": 0.3, "net_margin": 0.3, "pbv": 0.8, "per": 6, "revenue_yoy": 0.2}
    bad = {"roe": 0.01, "net_margin": 0.01, "pbv": 5.0, "per": 40, "revenue_yoy": -0.2}
    raw = {"LIQ": _raw(**good), "THIN": _raw(**good), "BAD": _raw(**bad)}
    traded = {"LIQ": 50e9, "THIN": 0.2e9, "BAD": 50e9}

    rec = score_universe(raw, traded)
    assert rec["LIQ"].rating == "Buy"
    assert rec["THIN"].rating == "Hold"
    assert rec["THIN"].score == rec["LIQ"].score  # score itself unchanged
    assert any("Thinly traded" in r for r in rec["THIN"].reasons)
    # Without liquidity data (e.g. pure scoring) nothing is capped.
    assert score_universe(raw)["THIN"].rating == "Buy"


def test_financials_skip_leverage_health_factors():
    from models import StockProfile

    bank = StockProfile(sector="Financial Services")
    f = _fund(total_liabilities=8_000.0, equity=1_000.0)  # bank-like leverage
    raw = raw_factors([100.0] * 70, [f], bank, price=100.0)
    assert raw["der"] is None and raw["equity_ratio"] is None
    assert raw["roe"] is not None  # quality/valuation still scored

    other = StockProfile(sector="Industrials")
    assert raw_factors([100.0] * 70, [f], other, price=100.0)["der"] == 8.0


def test_negative_equity_ranks_worst_not_missing():
    import math

    f = _fund(net_income=-500.0, total_assets=4_000.0, total_liabilities=5_000.0,
              equity=-1_000.0)
    raw = raw_factors([100.0] * 70, [f], None, price=100.0)
    # Previously: PBV dropped, D/E = -5 (looked best), RoE = +0.5 (loss / negative equity).
    assert raw["pbv"] == math.inf
    assert raw["der"] == math.inf
    assert raw["roe"] == -math.inf

    rec = score_universe({
        "BROKE": raw,
        "OK": _raw(roe=0.05, net_margin=0.02, pbv=3.0, der=2.0, equity_ratio=0.3),
    })
    def cat(t: str, name: str) -> float:
        score = next(c.score for c in rec[t].categories if c.name == name)
        assert score is not None
        return score
    assert cat("BROKE", "Valuation") < cat("OK", "Valuation")
    assert cat("BROKE", "Health") < cat("OK", "Health")

    from services.recommendation import _fmt

    assert "negative equity" in _fmt(math.inf, "ratio")  # shown instead of "inf"


def test_trader_factors_from_closes():
    from services.recommendation import trader_factors

    closes = [100.0] * 21 + [100.0 + i for i in range(1, 20)]  # steady climb to 119
    raw = trader_factors(closes)
    assert raw["from_high_20d"] == 0.0  # closing at the 20-day high
    assert raw["from_low_20d"] is not None and raw["from_low_20d"] > 0
    assert raw["volatility_20d"] is not None and raw["volatility_20d"] < 0.01
    # Not enough history -> nothing to score.
    assert all(v is None for v in trader_factors([100.0] * 10).values())


def test_trader_style_rates_liquid_price_only_stocks():
    from services.recommendation import trader_factors

    calm = [100.0 + (i % 2) * 0.5 for i in range(40)]
    wild = [100.0 * (1.08 if i % 2 else 0.93) for i in range(40)]
    raw = {"CALM": trader_factors(calm), "WILD": trader_factors(wild),
           "THIN": trader_factors(calm)}
    traded = {"CALM": 5e9, "WILD": 5e9, "THIN": 0.1e9}

    rec = score_universe(raw, traded, "trader")
    assert set(rec) == {"CALM", "WILD"}  # illiquid names are not rated for traders
    assert rec["CALM"].score > rec["WILD"].score  # stability is rewarded
    assert rec["CALM"].style == "trader"
    assert [c.name for c in rec["CALM"].categories] == ["Stability", "Setup"]
    # Investor style still refuses price-only data.
    assert score_universe({"CALM": _raw(ret_3m=0.1)}, traded, "investor") == {}


def test_52_week_position_ignores_older_history():
    from services.recommendation import _momentum

    last_year = [50.0 + (i % 51) for i in range(251)] + [75.0]  # range 50..100, ends at 75
    deep = [1000.0] * 3000 + last_year  # an old all-time high far above
    assert _momentum(deep)["pos_52w"] == _momentum(last_year)["pos_52w"] == 0.5


def test_investor_style_has_no_top_rating():
    from services.recommendation import _rating

    assert _rating(95, "investor") == "Buy"
    assert _rating(95, "trader") == "Strong Buy"
    assert _rating(10, "investor") == "Avoid"
