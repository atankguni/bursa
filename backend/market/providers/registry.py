"""Registry that resolves the active data provider(s) from config."""

from config import settings
from market.providers.base import MarketDataProvider
from market.providers.yahoo import YahooProvider

# name -> adapter class. Add new providers here.
_REGISTRY: dict[str, type[MarketDataProvider]] = {
    YahooProvider.name: YahooProvider,
}
_INSTANCES: dict[str, MarketDataProvider] = {}


def _resolve(name: str) -> MarketDataProvider:
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown data provider {name!r}. Available: {sorted(_REGISTRY)}"
        )
    if name not in _INSTANCES:
        _INSTANCES[name] = _REGISTRY[name]()
    return _INSTANCES[name]


def price_provider() -> MarketDataProvider:
    """Provider used for price bars (daily + intraday)."""
    return _resolve(settings.price_provider)


def fundamentals_provider() -> MarketDataProvider:
    """Provider used for statements / profile / FX."""
    return _resolve(settings.fundamentals_provider)


def available() -> list[dict]:
    """Every registered provider with its capability flags."""
    return [
        {"name": cls.name, "capabilities": sorted(cls.capabilities)}
        for cls in _REGISTRY.values()
    ]
