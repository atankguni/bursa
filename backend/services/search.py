"""Cached symbol search (debounced repeated queries; governed provider call)."""

import logging
import time

from config import settings
from market.providers.governor import governor
from market.providers.registry import price_provider

log = logging.getLogger("bursa.search")

# normalized query -> (fetched_at, results)
_cache: dict[str, tuple[float, list[dict]]] = {}


async def search(q: str, idf_only: bool = True) -> list[dict]:
    """
    Resolve a query to symbols, reusing a short-lived cache.

    `idf_only` (default) keeps only IDX (`.JK`) symbols. The raw provider result
    is cached, so switching the filter doesn't trigger another provider call.
    """
    query = q.strip().lower()
    if len(query) < 2:
        return []

    now = time.monotonic()
    cached = _cache.get(query)
    if cached and now - cached[0] < settings.search_cache_seconds:
        results = cached[1]
    else:
        provider = price_provider()
        results = await governor.call(
            provider.name, f"search:{query}", provider.search_symbols, q.strip()
        )
        _cache[query] = (now, results)

    if idf_only:
        return [r for r in results if str(r.get("symbol", "")).upper().endswith(".JK")]
    return results
