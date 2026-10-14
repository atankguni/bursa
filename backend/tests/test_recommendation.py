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
        "GOOD.JK": _raw(
            roe=0.25, net_margin=0.30, pbv=1.0, per=8, revenue_yoy=0.20,
            earnings_yoy=0.25, ret_3m=0.15, price_vs_sma50=0.08, pos_52w=0.9,
            der=0.3, equity_ratio=0.7,
        ),
        "MID.JK": _raw(
            roe=0.15, net_margin=0.15, pbv=2.0, per=15, revenue_yoy=0.08,
            earnings_yoy=0.10, ret_3m=0.03, price_vs_sma50=0.01, pos_52w=0.5,
            der=0.6, equity_ratio=0.5,
        ),
        "BAD.JK": _raw(
            roe=0.03, net_margin=0.02, pbv=4.0, per=30, revenue_yoy=-0.05,
            earnings_yoy=-0.10, ret_3m=-0.10, price_vs_sma50=-0.05, pos_52w=0.1,
            der=1.5, equity_ratio=0.25,
        ),
    }
    rec = score_universe(raw)

    assert rec["GOOD.JK"].score > rec["MID.JK"].score > rec["BAD.JK"].score
    assert rec["GOOD.JK"].rating in ("Strong Buy", "Buy")
    assert rec["BAD.JK"].rating in ("Reduce", "Avoid")
    assert rec["GOOD.JK"].coverage == 1.0
    assert rec["GOOD.JK"].disclaimer  # non-empty


def test_lower_is_better_for_valuation():
    # Identical except PBV: the cheaper stock must score higher on valuation.
    raw = {
        "CHEAP.JK": _raw(pbv=1.0),
        "PRICEY.JK": _raw(pbv=5.0),
    }
    rec = score_universe(raw)
    cheap_val = next(c for c in rec["CHEAP.JK"].categories if c.name == "Valuation")
    pricey_val = next(c for c in rec["PRICEY.JK"].categories if c.name == "Valuation")
    assert cheap_val.score > pricey_val.score


def test_sparse_data_lowers_coverage_and_strength():
    raw = {"THIN.JK": _raw(roe=0.2)}  # only 1 of 11 factors
    rec = score_universe(raw)["THIN.JK"]
    assert rec.coverage is not None and rec.coverage < 0.2
    assert rec.strength in ("Weak", "Moderate")


def test_raw_factors_from_fundamentals_and_prices():
    from models import Fundamental

    f = Fundamental(
        ticker="X.JK", fiscal_year=2024, financial_currency="IDR",
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
