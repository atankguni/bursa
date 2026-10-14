"""Unit tests for portfolio average-cost math (no DB)."""

from types import SimpleNamespace

from services.portfolio import apply_transactions


def T(side, qty, price, fees=0.0, ticker="X"):
    return SimpleNamespace(
        ticker=ticker, side=side, quantity=qty, price=price, fees=fees
    )


def test_buy_only_tracks_quantity_and_cost():
    books = apply_transactions([T("buy", 100, 1000)])
    b = books["X"]
    assert b["quantity"] == 100
    assert b["cost_basis"] == 100_000
    assert b["realized_pl"] == 0


def test_weighted_average_cost():
    books = apply_transactions([T("buy", 100, 1000), T("buy", 100, 2000)])
    b = books["X"]
    assert b["quantity"] == 200
    assert b["cost_basis"] == 300_000
    assert b["cost_basis"] / b["quantity"] == 1500  # average cost


def test_sell_realizes_profit_and_reduces_basis():
    books = apply_transactions(
        [T("buy", 100, 1000), T("buy", 100, 2000), T("sell", 100, 2500, fees=1000)]
    )
    b = books["X"]
    # proceeds 100*2500 - 1000 fees ; cost 1500*100 -> 99000 realized
    assert b["realized_pl"] == 99_000
    assert b["quantity"] == 100
    assert b["cost_basis"] == 150_000


def test_oversell_clamps_to_held():
    books = apply_transactions([T("buy", 100, 1000), T("sell", 200, 1200)])
    b = books["X"]
    assert b["quantity"] == 0
    assert b["cost_basis"] == 0
    # only the 100 held shares realize: 100*1200 - 100*1000 = 20000
    assert b["realized_pl"] == 20_000


def test_multiple_tickers_are_independent():
    books = apply_transactions(
        [T("buy", 10, 100, ticker="A"), T("buy", 5, 200, ticker="B")]
    )
    assert books["A"]["cost_basis"] == 1000
    assert books["B"]["cost_basis"] == 1000
