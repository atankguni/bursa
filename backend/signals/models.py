"""
signals/models.py
-----------------
Tables for signals. Conventions: models.py.
"""

from datetime import date

from sqlalchemy import Boolean, Date, Double, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from db.columns import stock_fk
from db.types import one_of
from schemas import InvestingStyle
from signals.schemas import Rating


class RatingSnapshot(Base):
    """
    The rating each stock had at a day's close, per investing style: the live
    track record (signals/track_record.py) compares it with what the price did
    next. Written once per trading day; shared market data, not per user.
    """

    __tablename__ = "rating_snapshots"
    __table_args__ = (one_of("style", InvestingStyle), one_of("rating", Rating))

    style: Mapped[InvestingStyle] = mapped_column(String(8), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    ticker: Mapped[str] = stock_fk(primary_key=True)
    rating: Mapped[Rating] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Double, nullable=False)
    # Traded >= recommendation_min_traded_value then (the backtest's "liquid").
    liquid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RatingSnapshot {self.day} {self.style} {self.ticker} {self.rating}>"
