"""
portfolio/models.py
-------------------
Tables for the portfolio and the watchlist. Conventions: models.py.
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, Double, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from db.columns import created_at_column, stock_fk, user_fk
from db.types import one_of
from portfolio.schemas import TradeSide


# --------------------------------------------------------------------------- #
# Per-user data
# --------------------------------------------------------------------------- #
class Watchlist(Base):
    """A ticker the user chose to follow."""

    __tablename__ = "watchlist"

    user_id: Mapped[int] = user_fk(primary_key=True)
    ticker: Mapped[str] = stock_fk(primary_key=True, index=True)
    added_at: Mapped[datetime] = created_at_column()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Watchlist {self.user_id} {self.ticker}>"


class Transaction(Base):
    """A buy/sell of a stock, used to derive the portfolio. Quantities are whole
    shares as traded; splits are applied when reading (market/corporate_actions)."""

    __tablename__ = "transactions"
    __table_args__ = (
        one_of("side", TradeSide),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("fees >= 0", name="fees_not_negative"),
        Index("ix_transactions_user_id_trade_date", "user_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk()
    ticker: Mapped[str] = stock_fk(index=True)
    side: Mapped[TradeSide] = mapped_column(String(4), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[float] = mapped_column(Double, nullable=False)
    fees: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Transaction {self.side} {self.quantity} {self.ticker}@{self.price}>"
