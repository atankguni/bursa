"""
services/data_version.py
------------------------
Cross-process cache invalidation. Each API process caches expensive results
(the scored universe). When the data behind one changes, whoever changed it
(often the worker, a different process) bumps a counter here; a cache entry
made under an older counter is stale. Reading the counter is one primary-key
lookup per request.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from db.upsert import upsert
from models import DataVersion
from schemas import DataName


async def current(session: AsyncSession, name: DataName) -> int:
    version = (
        await session.execute(select(DataVersion.version).where(DataVersion.name == name))
    ).scalar_one_or_none()
    return version or 0


async def bump(name: DataName) -> None:
    """Mark every cached copy of `name` stale (in all processes). Commits."""
    async with AsyncSessionLocal() as session:
        await upsert(session, DataVersion, {"name": name, "version": 0}, keys=["name"], update=[])
        await session.execute(
            update(DataVersion)
            .where(DataVersion.name == name)
            .values(version=DataVersion.version + 1)
        )
        await session.commit()
