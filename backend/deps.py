"""FastAPI dependencies: DB session and the signed-in user."""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.models import User, UserSession
from config import settings
from database import AsyncSessionLocal
from schemas import InvestingStyle


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield a scoped async DB session per request (shared by the request's dependencies)."""
    async with AsyncSessionLocal() as session:
        yield session


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name) or None


# 403 detail while an admin hasn't set up two-factor authentication yet.
MFA_SETUP_REQUIRED = "two_factor_setup_required"
# 403 detail while an admin's password is weak (they must change it first).
PASSWORD_CHANGE_REQUIRED = "password_change_required"
# 423 detail while the browser is locked after inactivity (password to unlock).
SESSION_LOCKED = "session_locked"


async def signed_in_session(
    request: Request, session: AsyncSession = Depends(get_session)
) -> tuple[UserSession, User]:
    """This browser's session and user, or 401, even while locked (for /me, unlock,
    lock and the activity report)."""
    from accounts.auth import session_for_token

    raw = session_token(request)
    found = await session_for_token(session, raw) if raw else None
    if found is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return found


async def signed_in_user(
    current: tuple[UserSession, User] = Depends(signed_in_session),
    session: AsyncSession = Depends(get_session),
) -> User:
    """The signed-in user, or 401 (423 while locked), without the admin policies
    below (for 2FA setup and changing the password)."""
    from accounts.auth import is_locked

    sess, user = current
    if await is_locked(session, sess, user):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=SESSION_LOCKED)
    return user


async def current_user(user: User = Depends(signed_in_user)) -> User:
    """The signed-in user, or 401. Every non-public router depends on this.
    Admins without two-factor authentication, or with a weak password, get 403
    until they fix it."""
    if user.mfa_setup_required:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MFA_SETUP_REQUIRED)
    if user.password_change_required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PASSWORD_CHANGE_REQUIRED
        )
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    """The signed-in user if they are an admin, or 403."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user


async def user_style(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> InvestingStyle:
    """The signed-in user's investing style (scores and signals depend on it)."""
    from accounts.preferences import get_investing_style

    return await get_investing_style(session, user.id)
