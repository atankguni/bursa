"""Tests for the provider registry and adapter contract."""

import pytest

from config import settings
from market.providers import registry
from market.providers.base import FUNDAMENTALS, PRICES, MarketDataProvider
from market.providers.yahoo import YahooProvider


def test_yahoo_is_registered_and_default():
    assert settings.price_provider == "yahoo"
    assert settings.fundamentals_provider == "yahoo"
    assert isinstance(registry.price_provider(), YahooProvider)
    assert isinstance(registry.fundamentals_provider(), YahooProvider)


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        MarketDataProvider()  # abstract methods not implemented


def test_yahoo_capabilities():
    caps = YahooProvider().capabilities
    assert {PRICES, FUNDAMENTALS} <= caps


def test_available_lists_providers_and_capabilities():
    items = registry.available()
    names = {i["name"] for i in items}
    assert "yahoo" in names
    yahoo = next(i for i in items if i["name"] == "yahoo")
    assert "prices" in yahoo["capabilities"]
    assert "fundamentals" in yahoo["capabilities"]


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "price_provider", "does-not-exist")
    with pytest.raises(ValueError, match="Unknown data provider"):
        registry.price_provider()
