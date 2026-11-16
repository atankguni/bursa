"""
Your own account (Settings → Profile and Your data): your name, your email
address (changed through a confirmation link sent to the new one), clearing your
portfolio, and deleting the account.

Opening the confirmation link needs no sign-in (it may be opened on another
device); everything else is for the signed-in user only.
"""

import html

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from accounts import auth, two_factor
from accounts.models import EmailChange, User
from accounts.routes.auth import log_event
from accounts.schemas import (
    ClearPortfolioIn,
    DeleteAccountIn,
    EmailChangeIn,
    EmailChangeOut,
    MeOut,
    NameIn,
)
from clock import utcnow
from config import settings
from deps import current_user, get_session
from mail.templates import layout
from portfolio.models import CashMovement, HoldingNote, Transaction

router = APIRouter(prefix="/api/account", tags=["account"])


def _bad_request(exc: auth.AuthError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --- name ----------------------------------------------------------------------
@router.put("/name", response_model=MeOut)
async def change_name(
    payload: NameIn, request: Request,
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user),
) -> MeOut:
    try:
        await auth.change_name(session, user, payload.name)
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    await log_event(session, user.id, "name_changed", request)
    return MeOut.model_validate(user)


# --- email ---------------------------------------------------------------------
async def _pending(session: AsyncSession, user_id: int) -> EmailChange | None:
    return (
        await session.execute(
            select(EmailChange).where(
                EmailChange.user_id == user_id,
                EmailChange.used_at.is_(None),
                EmailChange.expires_at > utcnow(),
            )
        )
    ).scalars().first()


@router.get("/email-change", response_model=EmailChangeOut | None)
async def pending_email_change(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user),
) -> EmailChangeOut | None:
    """A change waiting for its link to be opened, if any."""
    change = await _pending(session, user.id)
    return EmailChangeOut(new_email=change.new_email) if change else None


@router.post("/email-change", response_model=EmailChangeOut, status_code=202)
async def request_email_change(
    payload: EmailChangeIn, request: Request,
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user),
) -> EmailChangeOut:
    """Email a confirmation link to the new address; nothing changes until it's opened."""
    if not mail.configured():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email isn't set up on this server, so the new address can't be "
            "confirmed; ask your admin to change it.",
        )
    try:
        raw = await auth.request_email_change(
            session, user, payload.password, payload.new_email
        )
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    new_email = auth.normalize_email(payload.new_email)
    link = auth.link(f"/confirm-email/{raw}")
    hours = settings.email_change_hours
    text = (
        f"Hi {user.name},\n\nOpen this link to use {new_email} for your Bursa account. "
        f"It works once and expires in {hours} hours:\n\n{link}\n\n"
        "If you didn't ask for this, ignore this email; nothing changes."
    )
    body = (
        f"<p>Hi {html.escape(user.name)},</p><p>Open this link to use "
        f"<b>{html.escape(new_email)}</b> for your Bursa account. It works once and expires "
        f'in {hours} hours:</p><p><a href="{html.escape(link)}">Confirm this email</a></p>'
        "<p>If you didn't ask for this, ignore this email; nothing changes.</p>"
    )
    sent = await mail.send_quietly(mail.Email(
        subject="Confirm your new Bursa email", text=text,
        html=layout("Confirm your new email", body), to=(new_email,),
    ))
    if not sent:
        await session.execute(delete(EmailChange).where(EmailChange.user_id == user.id))
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The confirmation email couldn't be sent; try again later.",
        )
    await log_event(session, user.id, "email_change_requested", request, f"to {new_email}")
    await two_factor.notify(
        user, "Your Bursa email is being changed",
        f"Someone asked to change your Bursa account's email to {new_email}. It changes "
        "only when the link sent to that address is opened.",
    )
    return EmailChangeOut(new_email=new_email)


@router.delete("/email-change", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_email_change(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user),
) -> Response:
    await session.execute(
        delete(EmailChange).where(EmailChange.user_id == user.id, EmailChange.used_at.is_(None))
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/email-change/{token}", response_model=EmailChangeOut)
async def check_email_change(
    token: str, session: AsyncSession = Depends(get_session)
) -> EmailChangeOut:
    """Public: what the confirmation link would change (for its page)."""
    try:
        change, _ = await auth.open_email_change(session, token)
    except auth.AuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EmailChangeOut(new_email=change.new_email)


@router.post("/email-change/{token}", response_model=EmailChangeOut)
async def confirm_email_change(
    token: str, request: Request, session: AsyncSession = Depends(get_session)
) -> EmailChangeOut:
    """Public: opening the link proves the new address works; switch to it."""
    try:
        user, old = await auth.confirm_email_change(session, token)
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    await log_event(session, user.id, "email_changed", request, f"from {old}")
    # The old address hears about it too, in case this wasn't its owner.
    if mail.configured():
        await mail.send_quietly(mail.Email(
            subject="Your Bursa email was changed",
            text=f"Hi {user.name},\n\nYour Bursa account now uses {user.email} instead of this "
            "address. If this wasn't you, tell your Bursa admin.",
            html=layout(
                "Your Bursa email was changed",
                f"<p>Hi {html.escape(user.name)},</p><p>Your Bursa account now uses "
                f"<b>{html.escape(user.email)}</b> instead of this address.</p>"
                "<p>If this wasn't you, tell your Bursa admin.</p>",
            ),
            to=(old,),
        ))
    return EmailChangeOut(new_email=user.email)


# --- your data -----------------------------------------------------------------
@router.post("/clear-portfolio", status_code=status.HTTP_204_NO_CONTENT)
async def clear_portfolio(
    payload: ClearPortfolioIn, request: Request,
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user),
) -> Response:
    """Delete your transactions, cash movements and holding notes. The watchlist,
    alerts and settings stay."""
    if not auth.verify_password(user, payload.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password is incorrect")
    for model in (Transaction, CashMovement, HoldingNote):
        await session.execute(delete(model).where(model.user_id == user.id))
    await session.commit()
    await log_event(session, user.id, "portfolio_cleared", request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccountIn, response: Response,
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user),
) -> Response:
    """Delete your account and everything it owns, and sign out."""
    if not auth.verify_password(user, payload.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password is incorrect")
    try:
        await auth.check_can_leave(session, user)
    except auth.AuthError as exc:
        raise _bad_request(exc) from exc
    await session.delete(user)  # owned rows go with it (ON DELETE CASCADE + ORM cascade)
    await session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
