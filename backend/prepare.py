"""
prepare.py
----------
One-time preparation before the API and the worker start: the 2FA server
secret, schema migrations, the seeded catalog, and (fresh install) the setup
link for the first admin. Runs once per start, before uvicorn (see the
Dockerfile), so several API processes never migrate at the same time.

    python prepare.py
"""

import asyncio
import logging

from accounts.auth import ensure_setup_invite
from accounts.crypto import ensure_secret
from database import init_db
from market.bootstrap import seed

log = logging.getLogger("bursa.prepare")


async def prepare() -> None:
    ensure_secret()  # create the 2FA server secret before anything uses it
    await init_db()
    await seed()
    # Fresh install: log the one-time link that creates the first admin.
    await ensure_setup_invite()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    )
    # Alembic logs a line per autogenerate plugin on import; keep only migration work.
    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)
    asyncio.run(prepare())
    log.info("Database ready")
