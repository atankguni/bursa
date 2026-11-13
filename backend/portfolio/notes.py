"""
portfolio/notes.py
------------------
Holding notes: the user's reason for owning a stock, a target and a stop price,
and a review date. A note asks for attention ("flags") when the review date has
come, or the last close reached the target or fell to the stop. The Portfolio
page shows the flags; the daily email lists them for stocks still held.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from market.prices import latest_daily
from portfolio.models import HoldingNote
from portfolio.schemas import HoldingNoteOut, NoteFlag


def note_flags(
    target: float | None,
    stop: float | None,
    review_on: date | None,
    price: float | None,
    today: date,
) -> list[NoteFlag]:
    flags: list[NoteFlag] = []
    if review_on is not None and review_on <= today:
        flags.append("review_due")
    if price is not None:
        if target is not None and price >= target:
            flags.append("target_reached")
        if stop is not None and price <= stop:
            flags.append("stop_hit")
    return flags


async def list_notes(
    session: AsyncSession, user_id: int, today: date, tickers: set[str] | None = None
) -> list[HoldingNoteOut]:
    """The user's notes (optionally only for `tickers`), with the last close and flags."""
    q = select(HoldingNote).where(HoldingNote.user_id == user_id)
    if tickers is not None:
        q = q.where(HoldingNote.ticker.in_(tickers))
    notes = (await session.execute(q.order_by(HoldingNote.ticker))).scalars().all()
    quotes = await latest_daily(session, [n.ticker for n in notes])
    out: list[HoldingNoteOut] = []
    for n in notes:
        price = quotes[n.ticker].get("close") if n.ticker in quotes else None
        item = HoldingNoteOut.model_validate(n)
        item.last_price = price
        item.flags = note_flags(n.target, n.stop, n.review_on, price, today)
        out.append(item)
    return out
