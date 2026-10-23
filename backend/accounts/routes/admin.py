"""
Account administration (admins only): users, invites and reset links.

Links are shown to the admin once (only their hash is stored) and also emailed
when email is set up, so the app works with or without a mail provider.
"""

import html

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from accounts import auth, security_log, two_factor
from accounts.models import Invite, User
from accounts.routes.auth import log_event, send_reset_email
from accounts.schemas import (
    AdminSecurityEventOut,
    InviteIn,
    LinkOut,
    PendingInviteOut,
    UserOut,
    UserUpdateIn,
)
from config import settings
from deps import get_session, require_admin
from mail.templates import layout

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


async def _user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _keeps_an_admin(session: AsyncSession, user: User) -> None:
    """Refuse changes that would leave nobody able to administer the app."""
    if user.role == "admin" and user.is_active and await auth.active_admins(session) <= 1:
        raise HTTPException(status_code=400, detail="Keep at least one active admin")


@router.get("/users", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session)) -> list[UserOut]:
    rows = (await session.execute(select(User).order_by(User.created_at))).scalars().all()
    return [UserOut.model_validate(u) for u in rows]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, payload: UserUpdateIn, request: Request,
    session: AsyncSession = Depends(get_session), me: User = Depends(require_admin),
) -> UserOut:
    """Change role or disable/enable an account (disabling signs it out)."""
    user = await _user(session, user_id)
    if user.id == me.id:
        raise HTTPException(status_code=400, detail="You can't change your own account here")
    demote = payload.role is not None and payload.role != "admin"
    if demote or payload.is_active is False:
        await _keeps_an_admin(session, user)
    by = f"by {me.name}"
    if payload.role is not None and payload.role != user.role:
        user.role = payload.role
        await log_event(session, user.id, "role_changed", request, f"to {payload.role} {by}")
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        if not payload.is_active:
            await auth.revoke_sessions(session, user.id)
        kind = "account_enabled" if payload.is_active else "account_disabled"
        await log_event(session, user.id, kind, request, by)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int, session: AsyncSession = Depends(get_session), me: User = Depends(require_admin),
) -> Response:
    """Delete an account and everything it owns (watchlist, portfolio, alerts)."""
    user = await _user(session, user_id)
    if user.id == me.id:
        raise HTTPException(status_code=400, detail="You can't delete your own account")
    await _keeps_an_admin(session, user)
    await session.delete(user)  # owned rows go with it (ON DELETE CASCADE + ORM cascade)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/reset-link", response_model=LinkOut)
async def reset_link(
    user_id: int, request: Request,
    session: AsyncSession = Depends(get_session), me: User = Depends(require_admin),
) -> LinkOut:
    """A one-time password reset link for someone who forgot theirs."""
    user = await _user(session, user_id)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Enable the account first")
    link = auth.link(f"/reset/{await auth.create_reset(session, user)}")
    await log_event(session, user.id, "reset_link_created", request, f"by {me.name}")
    emailed = mail.configured() and await send_reset_email(user, link)
    return LinkOut(link=link, emailed=emailed)


@router.post("/users/{user_id}/reset-2fa", response_model=UserOut)
async def reset_two_factor(
    user_id: int, request: Request,
    session: AsyncSession = Depends(get_session), me: User = Depends(require_admin),
) -> UserOut:
    """For someone who lost their phone and recovery codes: turn their 2FA off so
    they can sign in with the password and set it up again (admins must, at once)."""
    user = await _user(session, user_id)
    if user.id == me.id:
        raise HTTPException(status_code=400, detail="Manage your own 2FA from your account")
    await two_factor.admin_reset(session, user)
    await log_event(session, user.id, "two_factor_reset", request, f"by {me.name}")
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.get("/security-log", response_model=list[AdminSecurityEventOut])
async def security_events(
    session: AsyncSession = Depends(get_session),
) -> list[AdminSecurityEventOut]:
    """The latest account activity of every user."""
    return await security_log.recent_all(session, limit=200)


@router.get("/invites", response_model=list[PendingInviteOut])
async def list_invites(session: AsyncSession = Depends(get_session)) -> list[PendingInviteOut]:
    rows = (await session.execute(
        select(Invite)
        .where(Invite.accepted_at.is_(None), Invite.email != "")
        .order_by(Invite.created_at.desc())
    )).scalars().all()
    return [PendingInviteOut.model_validate(i) for i in rows]


async def _send_invite(email: str, inviter: User, link: str) -> bool:
    who = html.escape(inviter.name)
    text = (
        f"{inviter.name} invited you to Bursa, an Indonesian stock market monitor.\n\n"
        f"Create your account here (the link works once and expires in "
        f"{settings.invite_days} days):\n\n{link}"
    )
    body = (
        f"<p>{who} invited you to Bursa, an Indonesian stock market monitor.</p>"
        f"<p>The link works once and expires in {settings.invite_days} days.</p>"
        f'<p><a href="{html.escape(link)}">Create your account</a></p>'
    )
    return await mail.send_quietly(mail.Email(
        subject="You're invited to Bursa", text=text,
        html=layout("You're invited", body), to=(email,),
    ))


@router.post("/invites", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteIn,
    session: AsyncSession = Depends(get_session), me: User = Depends(require_admin),
) -> LinkOut:
    try:
        raw = await auth.create_invite(session, payload.email, payload.role, me.id)
    except auth.AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    link = auth.link(f"/invite/{raw}")
    email = auth.normalize_email(payload.email)
    emailed = mail.configured() and await _send_invite(email, me, link)
    return LinkOut(link=link, emailed=emailed)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(invite_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    await session.execute(
        delete(Invite).where(Invite.id == invite_id, Invite.accepted_at.is_(None))
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
