"""
schemas.py
----------
Pydantic v2 response models for the public API surface.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StockBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str


class StockOut(StockBase):
    """A tracked stock enriched with its latest quote + daily change."""

    id: int
    indices: list[str] = []
    last_price: float | None = None
    previous_close: float | None = None
    change: float | None = None          # absolute point change vs prev close
    change_percent: float | None = None  # percentage change vs prev close
    volume: int | None = None
    updated_at: datetime | None = None


class PricePoint(BaseModel):
    """A single OHLCV bar for charting."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistory(BaseModel):
    """Full history payload for one ticker."""

    ticker: str
    name: str
    indices: list[str]
    interval: str
    points: list[PricePoint]
