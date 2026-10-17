"""
Account administration (admins only): users, invites and reset links.

Links are shown to the admin once (only their hash is stored) and also emailed
when email is set up, so the app works with or without a mail provider.
"""

import html

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import mail
from config import settings
from deps import get_session, require_admin
from mail.templates import layout
from models import Invite, User
from routers.auth import send_reset_email
from schemas import InviteIn, LinkOut, PendingInviteOut, UserOut, UserUpdateIn
from services import auth

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
    user_id: int, payload: UserUpdateIn,
    session: AsyncSession = Depends(get_session), me: User = Depends(require_admin),
) -> UserOut:
    """Change role or disable/enable an account (disabling signs it out)."""
    user = await _user(session, user_id)
    if user.id == me.id:
        raise HTTPException(status_code=400, detail="You can't change your own account here")
    demote = payload.role is not None and payload.role != "admin"
    if demote or payload.is_active is False:
        await _keeps_an_admin(session, user)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
        if not payload.is_active:
            await auth.revoke_sessions(session, user.id)
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
async def reset_link(user_id: int, session: AsyncSession = Depends(get_session)) -> LinkOut:
    """A one-time password reset link for someone who forgot theirs."""
    user = await _user(session, user_id)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Enable the account first")
    link = auth.link(f"/reset/{await auth.create_reset(session, user)}")
    emailed = mail.configured() and await send_reset_email(user, link)
    return LinkOut(link=link, emailed=emailed)


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
