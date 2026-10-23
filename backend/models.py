"""
models.py
---------
Every table, registered on `Base.metadata` (Alembic, the schema check and the
processes import this before the first query). The tables live with their
feature, in `<feature>/models.py`:

  accounts   users, sessions, invites, password resets, 2FA, settings, sign-in failures
  market     stocks, indices, bars, quotes, fundamentals, profiles, dividends, splits,
             per-stock sync state
  signals    rating snapshots (the live track record)
  portfolio  watchlist, transactions
  alerts     alerts, alert events, last-seen ratings
  assistant  chats, messages, daily usage
  system     the worker's heartbeat, scheduled jobs, worker tasks, data versions

Conventions
  * Stocks are referenced by code with ON UPDATE CASCADE: when IDX renames a
    code, updating `stocks.ticker` updates every table.
  * Points in time are `UTCDateTime` (aware UTC in Python); market days are `Date`.
  * Value sets are CHECK constraints generated from the `Literal`s in each feature's `schemas.py`.
  * Numbers use `Double` (8-byte): a 4-byte float would round large IDR figures.
    Doubles are exact for whole rupiah up to 9e15.
  * Composite natural keys instead of surrogate ids where rows are identified by
    them (bars, dividends, splits, memberships); `WITHOUT ROWID` on SQLite for the
    big bar tables, so rows are stored in key order with no extra index.
Column helpers shared by the features: db/columns.py.
"""

from accounts import models as accounts
from alerts import models as alerts
from assistant import models as assistant
from database import Base
from market import models as market
from portfolio import models as portfolio
from signals import models as signals
from system import models as system

# Base.metadata with every feature's tables loaded.
metadata = Base.metadata

__all__ = [
    "accounts", "alerts", "assistant", "market", "metadata", "portfolio", "signals", "system",
]
