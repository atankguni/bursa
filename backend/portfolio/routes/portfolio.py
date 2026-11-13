"""Portfolio endpoints: the signed-in user's transactions -> holdings + P/L."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.models import User
from clock import local_today
from deps import current_user, get_session
from market import index_quotes as index_service
from market.corporate_actions import adjusted_transactions
from market.models import Split, Stock
from portfolio.cash import cash_summary
from portfolio.dividend_calendar import dividend_calendar
from portfolio.dividend_income import dividend_income_by_month
from portfolio.holdings import build_portfolio, equity_curve
from portfolio.models import CashMovement, HoldingNote, Transaction
from portfolio.notes import list_notes
from portfolio.risk import portfolio_risk
from portfolio.schemas import (
    CashMovementIn,
    CashMovementOut,
    CashOut,
    DividendIncomeOut,
    EquityPoint,
    ExpectedDividendOut,
    HoldingNoteIn,
    HoldingNoteOut,
    PortfolioOut,
    PortfolioRiskOut,
    TaxSummaryOut,
    TransactionIn,
    TransactionOut,
)
from portfolio.tax import tax_summary
from schemas import StockCode

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# A split this close to recorded bonus shares is the same event.
BONUS_SPLIT_WINDOW = timedelta(days=45)


async def _held_quantity(session: AsyncSession, user_id: int, ticker: str) -> float:
    """Shares held now, in post-split terms (what a new sell is entered in)."""
    txs = await adjusted_transactions(session, user_id, ticker)
    return sum(t.quantity if t.side == "buy" else -t.quantity for t in txs)


@router.get("", response_model=PortfolioOut)
async def get_portfolio(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> PortfolioOut:
    totals, holdings = await build_portfolio(session, user.id)
    return PortfolioOut(
        totals=totals,
        holdings=holdings,
    )


@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[TransactionOut]:
    rows = (
        await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
        )
    ).scalars().all()
    return [TransactionOut.model_validate(r) for r in rows]


@router.post(
    "/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_transaction(
    payload: TransactionIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> TransactionOut:
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == payload.ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {payload.ticker}")

    if payload.kind == "bonus":
        # Yahoo lists some bonus issues as splits, which Bursa already applies to
        # every holding: recording them as well would count the shares twice.
        near = (
            await session.execute(
                select(Split.ex_date, Split.ratio).where(
                    Split.ticker == payload.ticker,
                    Split.ratio > 1,
                    Split.ex_date.between(
                        payload.trade_date - BONUS_SPLIT_WINDOW,
                        payload.trade_date + BONUS_SPLIT_WINDOW,
                    ),
                )
            )
        ).first()
        if near is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{payload.ticker} already has a split on {near.ex_date:%d %b %Y} "
                    f"({near.ratio:g} for 1) from the market data, which Bursa applies "
                    "to your shares automatically: no need to record the bonus shares."
                ),
            )

    if payload.side == "sell":
        held = await _held_quantity(session, user.id, payload.ticker)
        if payload.quantity > held + 1e-9:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell {payload.quantity}; only {held:g} held",
            )

    tx = Transaction(user_id=user.id, **payload.model_dump())
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.delete("/transactions/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    tx_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> Response:
    tx = (
        await session.execute(
            select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id)
        )
    ).scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await session.delete(tx)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[EquityPoint])
async def portfolio_history(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[EquityPoint]:
    # IHSG benchmark needs its history (fetched once, then stored).
    await index_service.ensure_full_history(session, "COMPOSITE")
    return await equity_curve(session, user.id)


@router.get("/risk", response_model=PortfolioRiskOut)
async def get_portfolio_risk(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> PortfolioRiskOut:
    """Concentration, sectors, beta vs IHSG, stress test and max drawdown."""
    await index_service.ensure_full_history(session, "COMPOSITE")
    return PortfolioRiskOut.model_validate(await portfolio_risk(session, user.id))


@router.get("/dividend-calendar", response_model=list[ExpectedDividendOut])
async def get_dividend_calendar(
    days: int = Query(180, ge=7, le=366),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[ExpectedDividendOut]:
    """Expected ex-dates for holdings + watchlist, projected from last year's."""
    calendar = await dividend_calendar(session, user.id, days)
    return [ExpectedDividendOut.model_validate(d) for d in calendar]


@router.get("/dividend-income", response_model=DividendIncomeOut)
async def get_dividend_income(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> DividendIncomeOut:
    """Net dividends per month: received over the last 12, expected over the next 6."""
    return await dividend_income_by_month(session, user.id)


@router.get("/tax-summary", response_model=TaxSummaryOut)
async def get_tax_summary(
    year: int = Query(ge=2000, le=2100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> TaxSummaryOut:
    """A year's holdings on 31 December, sales and dividends, for the SPT."""
    if year > local_today().year:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That year hasn't started yet")
    return await tax_summary(session, user.id, year)


# --------------------------------------------------------------------------- #
# Cash (RDN)
# --------------------------------------------------------------------------- #


@router.get("/cash", response_model=CashOut)
async def get_cash(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> CashOut:
    """Cash balance (deposits, withdrawals, trades, dividends) and return on it."""
    return await cash_summary(session, user.id)


@router.post("/cash", response_model=CashMovementOut, status_code=status.HTTP_201_CREATED)
async def add_cash_movement(
    payload: CashMovementIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> CashMovementOut:
    if payload.day > local_today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That date is in the future")
    row = CashMovement(user_id=user.id, **payload.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return CashMovementOut.model_validate(row)


@router.delete("/cash/{movement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cash_movement(
    movement_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> Response:
    row = (
        await session.execute(
            select(CashMovement).where(
                CashMovement.id == movement_id, CashMovement.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Holding notes
# --------------------------------------------------------------------------- #


@router.get("/notes", response_model=list[HoldingNoteOut])
async def get_notes(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> list[HoldingNoteOut]:
    """Your notes per stock, with the last close and what needs attention."""
    return await list_notes(session, user.id, local_today())


@router.put("/notes/{ticker}", response_model=HoldingNoteOut)
async def put_note(
    ticker: StockCode,
    payload: HoldingNoteIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> HoldingNoteOut:
    """Create or replace the note on `ticker`."""
    if await session.get(Stock, ticker) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown ticker: {ticker}")
    note = await session.get(HoldingNote, (user.id, ticker))
    if note is None:
        note = HoldingNote(user_id=user.id, ticker=ticker)
        session.add(note)
    note.thesis = (payload.thesis or "").strip() or None
    note.target, note.stop, note.review_on = payload.target, payload.stop, payload.review_on
    await session.commit()
    [out] = await list_notes(session, user.id, local_today(), {ticker})
    return out


@router.delete("/notes/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    ticker: StockCode,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> Response:
    note = await session.get(HoldingNote, (user.id, ticker))
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await session.delete(note)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
