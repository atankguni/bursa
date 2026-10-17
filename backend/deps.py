"""FastAPI dependencies: DB session and the signed-in user."""

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import AsyncSessionLocal
from models import User
from schemas import InvestingStyle


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield a scoped async DB session per request (shared by the request's dependencies)."""
    async with AsyncSessionLocal() as session:
        yield session


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name) or None


async def current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    """The signed-in user, or 401. Every non-public router depends on this."""
    from services.auth import user_for_token

    raw = session_token(request)
    user = await user_for_token(session, raw) if raw else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
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
    from services.preferences import get_investing_style

    return await get_investing_style(session, user.id)
