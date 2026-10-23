"""
alerts/schemas.py
-----------------
API models (Pydantic) for alerts.
"""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict

from schemas import Schema, StockCode

# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #

AlertType = Literal[
    "price_above", "price_below", "pct_change", "rating_change",
    # Expected dividend: threshold = days ahead of the (estimated) cum date, default 3.
    "dividend_soon",
]


class AlertIn(Schema):
    ticker: StockCode
    type: AlertType
    threshold: float | None = None


class AlertOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    type: AlertType
    threshold: float | None = None
    active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime


class AlertEventOut(Schema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    ticker: str
    triggered_at: datetime
    value: float | None = None
    message: str


class NotificationStatusOut(Schema):
    """Which out-of-app channels are configured (and whether a test was delivered)."""

    telegram: bool
    delivered: bool | None = None
