"""Unit tests for alert rule evaluation (pure)."""

from alerts.service import evaluate_alert


def test_price_above():
    assert evaluate_alert("price_above", 90, 100, 95, None, None) == (True, 100)
    assert evaluate_alert("price_above", 110, 100, 95, None, None) == (False, None)


def test_price_below():
    assert evaluate_alert("price_below", 110, 100, 95, None, None) == (True, 100)
    assert evaluate_alert("price_below", 90, 100, 95, None, None) == (False, None)


def test_pct_change_up_and_down():
    assert evaluate_alert("pct_change", 5, 110, 100, None, None) == (True, 10.0)
    assert evaluate_alert("pct_change", 5, 90, 100, None, None) == (True, -10.0)
    assert evaluate_alert("pct_change", 20, 110, 100, None, None) == (False, None)


def test_rating_change():
    assert evaluate_alert("rating_change", None, 100, 99, "Buy", "Hold") == (True, None)
    assert evaluate_alert("rating_change", None, 100, 99, "Buy", "Buy") == (False, None)
    # No baseline yet -> no trigger.
    assert evaluate_alert("rating_change", None, 100, 99, "Buy", None) == (False, None)


def test_missing_data_never_triggers():
    assert evaluate_alert("price_above", 1, None, None, None, None) == (False, None)
    assert evaluate_alert("pct_change", 5, 100, None, None, None) == (False, None)
