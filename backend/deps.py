"""FastAPI dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield a scoped async DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session
