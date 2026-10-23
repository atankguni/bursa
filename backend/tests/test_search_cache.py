"""Tests for the cached symbol search."""

import services.search as search_mod
from config import settings


class _FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def search_symbols(self, q: str) -> list[dict]:
        self.calls += 1
        return [{"symbol": q.upper(), "name": q, "exchange": "JK", "type": "EQUITY", "idx": True}]


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


class _MixedProvider:
    name = "fake"

    def search_symbols(self, q: str) -> list[dict]:
        return [
            {"symbol": "BBCA", "name": "Bank Central Asia",
             "exchange": "Jakarta", "type": "EQUITY", "idx": True},
            {"symbol": "PBCRY", "name": "Bank Central Asia OTC",
             "exchange": "OTC", "type": "EQUITY", "idx": False},
        ]


async def test_search_defaults_to_idx_only(monkeypatch):
    monkeypatch.setattr(settings, "provider_min_interval_ms", 0)
    monkeypatch.setattr(search_mod, "price_provider", lambda: _MixedProvider())
    search_mod._cache.clear()

    idx_only = await search_mod.search("bank", idf_only=True)
    all_exchanges = await search_mod.search("bank", idf_only=False)

    assert [r["symbol"] for r in idx_only] == ["BBCA"]
    assert len(all_exchanges) == 2
