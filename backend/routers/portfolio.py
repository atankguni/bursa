"""Portfolio endpoints (transactions -> holdings + P/L)."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_session
from models import Stock, Transaction
from schemas import EquityPoint, PortfolioOut, TransactionIn, TransactionOut
from services.portfolio import build_portfolio, equity_curve

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


async def _held_quantity(session: AsyncSession, ticker: str) -> float:
    buys = (
        await session.execute(
            select(func.coalesce(func.sum(Transaction.quantity), 0.0)).where(
                Transaction.ticker == ticker, Transaction.side == "buy"
            )
        )
    ).scalar_one()
    sells = (
        await session.execute(
            select(func.coalesce(func.sum(Transaction.quantity), 0.0)).where(
                Transaction.ticker == ticker, Transaction.side == "sell"
            )
        )
    ).scalar_one()
    return float(buys) - float(sells)


@router.get("", response_model=PortfolioOut)
async def get_portfolio(session: AsyncSession = Depends(get_session)) -> PortfolioOut:
    totals, holdings = await build_portfolio(session)
    return PortfolioOut(totals=totals, holdings=holdings)


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
    return [EquityPoint(**p) for p in await equity_curve(session)]
