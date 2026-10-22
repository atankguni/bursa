# Local type stubs for yfinance (it ships none). Only what Bursa uses
# (market/providers/yahoo.py); Yahoo's JSON stays `Any` and is parsed there.
from collections.abc import Mapping
from typing import Any

import pandas as pd

def set_tz_cache_location(cache_dir: str) -> None: ...
def download(
    tickers: str | list[str],
    *,
    period: str | None = ...,
    interval: str = ...,
    group_by: str = ...,
    auto_adjust: bool = ...,
    progress: bool = ...,
    threads: bool = ...,
    prepost: bool = ...,
) -> pd.DataFrame | None: ...

class Ticker:
    def __init__(self, ticker: str) -> None: ...
    @property
    def info(self) -> dict[str, Any]: ...
    @property
    def fast_info(self) -> Mapping[str, Any]: ...
    @property
    def income_stmt(self) -> pd.DataFrame | None: ...
    @property
    def balance_sheet(self) -> pd.DataFrame | None: ...
    @property
    def splits(self) -> pd.Series[float] | None: ...
    @property
    def dividends(self) -> pd.Series[float] | None: ...

class Search:
    quotes: list[dict[str, Any]]
    def __init__(self, query: str, max_results: int = ...) -> None: ...
