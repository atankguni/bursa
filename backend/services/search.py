"""Cached symbol search (debounced repeated queries; governed provider call)."""

import logging
import time

from config import settings
from market.providers.governor import governor
from market.providers.registry import price_provider

log = logging.getLogger("bursa.search")

# normalized query -> (fetched_at, results)
_cache: dict[str, tuple[float, list[dict]]] = {}


async def search(q: str) -> list[dict]:
    """Resolve a query to symbols, reusing a short-lived cache."""
    query = q.strip().lower()
    if len(query) < 2:
        return []

    now = time.monotonic()
    cached = _cache.get(query)
    if cached and now - cached[0] < settings.search_cache_seconds:
        return cached[1]

    provider = price_provider()
    results = await governor.call(
        provider.name, f"search:{query}", provider.search_symbols, q.strip()
    )
    _cache[query] = (now, results)
    return results
