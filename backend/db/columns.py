"""
db/columns.py
-------------
Column definitions the feature models share: references to a stock and to a
user, and created / updated timestamps.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from clock import utcnow
from db.types import UTCDateTime


def stock_fk(*, primary_key: bool = False, index: bool = False) -> Mapped[str]:
    """A stock code column referencing `stocks.ticker` (follows renames, deleted with it)."""
    return mapped_column(
        String(12),
        ForeignKey("stocks.ticker", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=primary_key,
        index=index,
        nullable=False,
    )


def user_fk(*, primary_key: bool = False, index: bool = False) -> Mapped[int]:
    return mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=primary_key,
        index=index,
        nullable=False,
    )


def created_at_column() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=utcnow, nullable=False)


def updated_at_column() -> Mapped[datetime]:
    return mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
