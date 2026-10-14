"""Tests for the cached symbol search."""

import services.search as search_mod
from config import settings


class _FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def search_symbols(self, q: str) -> list[dict]:
        self.calls += 1
        return [{"symbol": f"{q.upper()}.JK", "name": q, "exchange": "JK", "type": "EQUITY"}]


async def test_search_is_cached_and_normalized(monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    fake = _FakeProvider()
    monkeypatch.setattr(search_mod, "price_provider", lambda: fake)
    search_mod._cache.clear()

    first = await search_mod.search("bbca")
    second = await search_mod.search("BBCA")  # same query, different case

    assert first == second
    assert fake.calls == 1  # second call served from cache


async def test_search_requires_min_length(monkeypatch):
    fake = _FakeProvider()
    monkeypatch.setattr(search_mod, "price_provider", lambda: fake)
    search_mod._cache.clear()

    assert await search_mod.search("b") == []
    assert fake.calls == 0
