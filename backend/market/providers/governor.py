"""
market/providers/governor.py
----------------------------
Central governor for every outbound provider (Yahoo) call.

Goals (avoid rate-limit / blacklisting):
  * Cap concurrency.
  * Space calls at a minimum interval.
  * Single-flight: concurrent identical calls share one execution.
  * Record lightweight metrics for observability.

All provider calls go through `governor.call(...)`, so bursts are impossible no
matter how many endpoints or jobs trigger them. The governor is per process:
the worker makes nearly all calls (syncs); an API process only makes the few
a user's click needs (search, a chart's full history, adding a stock). Its
counters reach the API through system/worker_state.py.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from clock import local_today
from config import settings
from market.schemas import ProviderStat

log = logging.getLogger("bursa.governor")


class Governor:
    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(settings.provider_max_concurrency)
        self._pace_lock = asyncio.Lock()
        self._last_start = 0.0
        self._inflight: dict[str, asyncio.Future[Any]] = {}
        self._metrics: dict[str, ProviderStat] = {}
        self._daily: dict[str, int] = {}
        self._day = local_today()

    # -- metrics --------------------------------------------------------------
    def _stat(self, provider: str) -> ProviderStat:
        return self._metrics.setdefault(
            provider,
            ProviderStat(calls=0, errors=0, last_error=None, last_call_at=None),
        )

    def _roll(self) -> None:
        today = local_today()
        if today != self._day:
            self._day = today
            self._daily = {}

    def stats(self) -> dict[str, ProviderStat]:
        """Per-provider metrics + today's call count (for /api/providers)."""
        self._roll()
        return {
            name: stat.model_copy(update={"calls_today": self._daily.get(name, 0)})
            for name, stat in self._metrics.items()
        }

    def reset_daily(self) -> None:
        self._daily = {}

    # -- pacing ---------------------------------------------------------------
    async def _pace(self) -> None:
        interval = settings.provider_min_interval_ms / 1000
        async with self._pace_lock:
            now = time.monotonic()
            wait = self._last_start + interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_start = time.monotonic()

    # -- public API -----------------------------------------------------------
    async def call[**P, T](
        self,
        provider: str,
        key: str,
        fn: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """
        Run a blocking provider call under the governor.

        Identical in-flight `key`s are deduped (single-flight).
        """
        existing = self._inflight.get(key)
        if existing is not None:
            return await existing  # same key -> same call -> same result type

        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        self._inflight[key] = future
        stat = self._stat(provider)

        try:
            async with self._sem:
                await self._pace()
                result = await asyncio.to_thread(fn, *args, **kwargs)
            stat.calls += 1
            stat.last_call_at = time.time()
            stat.last_error = None
            self._daily[provider] = self._daily.get(provider, 0) + 1
            future.set_result(result)
            return result
        except Exception as exc:  # noqa: BLE001 - surface to caller
            stat.errors += 1
            stat.last_error = str(exc)
            future.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)


governor = Governor()
