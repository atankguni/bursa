"""Valuation metrics derived from price + fundamentals (pure functions)."""

from market.models import Fundamental
from market.schemas import DerivedMetrics


def _book_value(f: Fundamental) -> float | None:
    """Total equity: assets - liabilities, falling back to shareholders' equity."""
    if f.total_assets is not None and f.total_liabilities is not None:
        return f.total_assets - f.total_liabilities
    return f.equity


def derive_metrics(price: float | None, f: Fundamental | None) -> DerivedMetrics:
    """
    Compute market cap, book value, PBV and RoE from a price + a fundamentals row.

    All monetary inputs are expected to already be in the trading currency (IDR),
    so the ratios are meaningful regardless of the filer's reporting currency.
    """
    if f is None:
        return DerivedMetrics()

    market_cap = price * f.total_shares if price is not None and f.total_shares else None
    book_value = _book_value(f)

    pbv = (
        round(market_cap / book_value, 3)
        if market_cap and book_value and book_value > 0
        else None
    )
    # RoE is meaningless on non-positive equity (a loss over negative equity
    # would read as a large *positive* return), so it is left blank there.
    roe = (
        round(f.net_income / f.equity, 4)
        if f.net_income is not None and f.equity is not None and f.equity > 0
        else None
    )
    return DerivedMetrics(market_cap=market_cap, book_value=book_value, pbv=pbv, roe=roe)
