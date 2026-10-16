"""Portfolio endpoints (transactions -> holdings + P/L)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from models import Stock, Transaction
from schemas import (
    EquityPoint,
    ExpectedDividendOut,
    HoldingOut,
    PortfolioOut,
    PortfolioRiskOut,
    PortfolioTotals,
    TransactionIn,
    TransactionOut,
)
from services import indices as index_service
from services.corporate_actions import adjusted_transactions
from services.dividend_calendar import dividend_calendar
from services.portfolio import build_portfolio, equity_curve
from services.portfolio_risk import portfolio_risk

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


async def _held_quantity(session: AsyncSession, ticker: str) -> float:
    """Shares held now, in post-split terms (what a new sell is entered in)."""
    txs = await adjusted_transactions(session, ticker)
    return sum(t.quantity if t.side == "buy" else -t.quantity for t in txs)


@router.get("", response_model=PortfolioOut)
async def get_portfolio(session: AsyncSession = Depends(get_session)) -> PortfolioOut:
    totals, holdings = await build_portfolio(session)
    return PortfolioOut(
        totals=PortfolioTotals(**totals),
        holdings=[HoldingOut(**h) for h in holdings],
    )


@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(
    session: AsyncSession = Depends(get_session),
) -> list[TransactionOut]:
    rows = (
        await session.execute(
            select(Transaction).order_by(Transaction.trade_date.desc(), Transaction.id.desc())
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
) -> TransactionOut:
    stock = (
        await session.execute(select(Stock).where(Stock.ticker == payload.ticker))
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker: {payload.ticker}")

    if payload.side == "sell":
        held = await _held_quantity(session, payload.ticker)
        if payload.quantity > held + 1e-9:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot sell {payload.quantity}; only {held:g} held",
            )

    tx = Transaction(**payload.model_dump())
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return TransactionOut.model_validate(tx)


@router.delete("/transactions/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    tx_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    tx = (
        await session.execute(select(Transaction).where(Transaction.id == tx_id))
    ).scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await session.delete(tx)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[EquityPoint])
async def portfolio_history(
    session: AsyncSession = Depends(get_session),
) -> list[EquityPoint]:
    # IHSG benchmark needs its history (fetched once, then stored).
    await index_service.ensure_full_history(session, "COMPOSITE")
    return [EquityPoint(**p) for p in await equity_curve(session)]


@router.get("/risk", response_model=PortfolioRiskOut)
async def get_portfolio_risk(session: AsyncSession = Depends(get_session)) -> PortfolioRiskOut:
    """Concentration, sectors, beta vs IHSG, stress test and max drawdown."""
    await index_service.ensure_full_history(session, "COMPOSITE")
    return PortfolioRiskOut.model_validate(await portfolio_risk(session))


@router.get("/dividend-calendar", response_model=list[ExpectedDividendOut])
async def get_dividend_calendar(
    days: int = Query(180, ge=7, le=366),
    session: AsyncSession = Depends(get_session),
) -> list[ExpectedDividendOut]:
    """Expected ex-dates for holdings + watchlist, projected from last year's."""
    return [ExpectedDividendOut.model_validate(d) for d in await dividend_calendar(session, days)]
