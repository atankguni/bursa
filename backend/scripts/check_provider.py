"""
Check that the market-data provider (Yahoo) answers from this machine.

Run it on a new server BEFORE moving Bursa there: Yahoo throttles some
datacenter addresses much more than home connections, and every price,
chart and statement in Bursa comes from it. A handful of calls, like the
regular syncs make; no database needed.

    docker compose run --rm --no-deps backend python -m scripts.check_provider

Exit code 0 when everything answered, 1 otherwise.
"""

import sys
import time
from collections.abc import Callable
from typing import Any

from market.providers.registry import fundamentals_provider, price_provider

TICKERS = ["BBCA", "BBRI", "TLKM", "ASII", "BMRI", "UNVR", "ANTM", "ICBP", "ADRO", "GOTO"]


def _check(label: str, call: Callable[[], Any], count: Callable[[Any], int]) -> bool:
    started = time.monotonic()
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001 - report every failure the same way
        print(f"FAIL  {label}: {type(exc).__name__}: {exc}")
        return False
    n = count(result)
    took = time.monotonic() - started
    ok = n > 0
    print(f"{'ok  ' if ok else 'FAIL'}  {label}: {n} rows in {took:.1f}s")
    return ok


def main() -> int:
    prices = price_provider()
    funds = fundamentals_provider()
    print(f"Provider: {prices.name} (prices), {funds.name} (fundamentals)\n")
    results = [
        _check(
            f"daily prices, {len(TICKERS)} stocks, 1 month",
            lambda: prices.fetch_price_rows(TICKERS, "1mo", "1d"),
            lambda r: sum(1 for bars in r.values() if bars),
        ),
        _check(
            "intraday 1-minute bars, 3 stocks",
            lambda: prices.fetch_price_rows(TICKERS[:3], "5d", "1m"),
            lambda r: sum(len(bars) for bars in r.values()),
        ),
        _check(
            "index quote (IHSG)",
            lambda: prices.fetch_index_quotes(["^JKSE"]),
            len,
        ),
        _check(
            "fundamentals (BBCA statements)",
            lambda: funds.fetch_fundamentals("BBCA"),
            lambda r: len(r[0]),
        ),
        _check("dividends (TLKM)", lambda: funds.fetch_dividends("TLKM"), len),
    ]
    passed = sum(results)
    print()
    if passed == len(results):
        print("All checks passed: Yahoo answers from this machine.")
        return 0
    print(
        f"{len(results) - passed} of {len(results)} checks failed. If they keep failing "
        "(try again in an hour), Yahoo is blocking this server's address: pick another "
        "provider or region before moving Bursa here."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
