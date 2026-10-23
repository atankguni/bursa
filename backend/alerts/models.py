"""
alerts/models.py
----------------
Tables for alerts. Conventions: models.py.
"""

from datetime import datetime

from sqlalchemy import Boolean, Double, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from alerts.schemas import AlertType
from database import Base
from db.columns import created_at_column, stock_fk, updated_at_column, user_fk
from db.types import UTCDateTime, one_of
from signals.schemas import Rating, Strength


class Alert(Base):
    """A user-defined alert rule on a ticker."""

    __tablename__ = "alerts"
    __table_args__ = (one_of("type", AlertType),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk(index=True)
    ticker: Mapped[str] = stock_fk(index=True)
    type: Mapped[AlertType] = mapped_column(String(16), nullable=False)
    threshold: Mapped[float | None] = mapped_column(Double, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Alert {self.ticker} {self.type} {self.threshold}>"


class AlertEvent(Base):
    """A triggered alert (kept for the in-app notification list)."""

    __tablename__ = "alert_events"
    __table_args__ = (Index("ix_alert_events_user_id_triggered_at", "user_id", "triggered_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = user_fk()
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = stock_fk(index=True)
    triggered_at: Mapped[datetime] = created_at_column()
    value: Mapped[float | None] = mapped_column(Double, nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AlertEvent {self.ticker} {self.triggered_at}>"


class RatingState(Base):
    """
    Last-seen rating per (user, ticker), for rating-change alerts. Per user
    because ratings depend on each user's investing style. Derived data: missing
    rows are rebuilt (as a baseline, without alerting) on the next evaluation.
    """

    __tablename__ = "rating_state"
    __table_args__ = (one_of("rating", Rating), one_of("strength", Strength))

    user_id: Mapped[int] = user_fk(primary_key=True)
    ticker: Mapped[str] = stock_fk(primary_key=True, index=True)
    rating: Mapped[Rating] = mapped_column(String(16), nullable=False)
    strength: Mapped[Strength | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = updated_at_column()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RatingState {self.user_id} {self.ticker} {self.rating}>"
