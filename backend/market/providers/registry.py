"""Registry that resolves the active data provider(s) from config."""

import importlib
from typing import TypedDict

from config import settings
from market.providers.base import MarketDataProvider

# name -> "module:Class". Add new providers here. Imported on first use: the
# Yahoo adapter brings yfinance, pandas and numpy (~85 MB of memory, 1-2 s to
# load), which the API process only needs once a request reaches Yahoo (search,
# stale fundamentals, deep chart history).
_REGISTRY: dict[str, str] = {
    "yahoo": "market.providers.yahoo:YahooProvider",
}
_INSTANCES: dict[str, MarketDataProvider] = {}


def _class(name: str) -> type[MarketDataProvider]:
    module, _, attr = _REGISTRY[name].partition(":")
    return getattr(importlib.import_module(module), attr)


class ProviderEntry(TypedDict):
    name: str
    capabilities: list[str]


def _resolve(name: str) -> MarketDataProvider:
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown data provider {name!r}. Available: {sorted(_REGISTRY)}"
        )
    if name not in _INSTANCES:
        _INSTANCES[name] = _class(name)()
    return _INSTANCES[name]


def price_provider() -> MarketDataProvider:
    """Provider used for price bars (daily + intraday)."""
    return _resolve(settings.price_provider)


def fundamentals_provider() -> MarketDataProvider:
    """Provider used for statements / profile / FX."""
    return _resolve(settings.fundamentals_provider)


def available() -> list[ProviderEntry]:
    """Every registered provider with its capability flags (imports them)."""
    return [
        {"name": name, "capabilities": sorted(_class(name).capabilities)}
        for name in _REGISTRY
    ]
