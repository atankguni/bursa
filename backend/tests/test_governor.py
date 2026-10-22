"""Tests for the outbound provider governor (concurrency, pacing, single-flight)."""

import asyncio
import time

import pytest

from config import settings
from market.providers.governor import Governor


def _counter_fn():
    state = {"calls": 0, "active": 0, "max_active": 0}

    def fn():
        state["calls"] += 1
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.05)
        state["active"] -= 1
        return state["calls"]

    return state, fn


async def test_single_flight_dedupes_concurrent_calls(monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    g = Governor()
    state, fn = _counter_fn()

    results = await asyncio.gather(*[g.call("p", "same-key", fn) for _ in range(6)])

    assert state["calls"] == 1  # one execution shared by all callers
    assert results == [1] * 6


async def test_concurrency_cap(monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    monkeypatch.setattr(settings, "provider_max_concurrency", 2)
    g = Governor()
    state, fn = _counter_fn()

    await asyncio.gather(*[g.call("p", f"k{i}", fn) for i in range(6)])

    assert state["calls"] == 6
    assert state["max_active"] <= 2


async def test_pacing_spaces_calls(monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 50)
    g = Governor()

    t0 = time.monotonic()
    await asyncio.gather(
        g.call("p", "a", lambda: 1),
        g.call("p", "b", lambda: 1),
        g.call("p", "c", lambda: 1),
    )
    elapsed = time.monotonic() - t0

    # Three calls, spaced 50ms apart -> at least two intervals.
    assert elapsed >= 0.09


async def test_metrics_record_calls_and_errors(monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    g = Governor()

    def boom():
        raise ValueError("boom")

    await g.call("p", "ok", lambda: 1)
    with pytest.raises(ValueError):
        await g.call("p", "err", boom)

    stat = g.stats()["p"]
    assert stat.calls == 1
    assert stat.calls_today == 1
    assert stat.errors == 1
    assert stat.last_error == "boom"
