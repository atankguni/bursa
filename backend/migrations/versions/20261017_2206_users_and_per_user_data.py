"""Accounts (invite-only login) and per-user data.

* New tables: users, sessions, invites, password_resets, user_preferences.
* watchlist, transactions, alerts, alert_events get a nullable `user_id`.
  Existing rows keep NULL until the first admin account claims them
  (services/auth.claim_orphans), so a single-user install keeps its data.
* preferences (one global row per key) -> user_preferences (copied, unowned).
* rating_state is rebuilt per user. It only holds derived snapshots, so it is
  recreated empty; the next alert evaluation stores fresh baselines.

Downgrade removes accounts and every row that belongs to one.

Revision ID: 20261017_220600
Revises: 20261017_211400
Create Date: 2026-10-17 22:06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from alembic.operations import BatchOperations

revision: str = "20261017_220600"
down_revision: str | None = "20261017_211400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED = ("watchlist", "transactions", "alerts", "alert_events")


def _prefs(name: str, *extra: sa.ColumnClause[object]) -> sa.TableClause:
    # Lightweight table handles: SQLAlchemy quotes `key` (reserved in MySQL).
    return sa.table(name, sa.column("key"), sa.column("value"), sa.column("updated_at"), *extra)


def _copy_preferences(
    src: sa.TableClause, dst: sa.TableClause, *where: sa.ColumnElement[bool]
) -> None:
    cols = ["key", "value", "updated_at"]
    op.execute(
        dst.insert().from_select(cols, sa.select(*(src.c[c] for c in cols)).where(*where))
    )


def _owner(batch_op: BatchOperations, table: str) -> None:
    batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
    batch_op.create_index(f"ix_{table}_user_id", ["user_id"], unique=False)
    batch_op.create_foreign_key(
        f"fk_{table}_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)

    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], name="fk_invites_invited_by",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_invites_token_hash"),
    )
    op.create_index("ix_invites_email", "invites", ["email"], unique=False)

    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_password_resets_user_id",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_resets_token_hash"),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"], unique=False)

    # preferences -> user_preferences (unowned until the first admin claims them).
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_preferences_user_id",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_preference"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=False)
    _copy_preferences(_prefs("preferences"), _prefs("user_preferences"))
    op.drop_table("preferences")

    # rating_state: derived snapshots, now per user -> recreate empty.
    op.drop_table("rating_state")
    op.create_table(
        "rating_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("strength", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"], name="fk_rating_state_ticker",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_rating_state_user_id",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_rating_state"),
    )

    for table in ("transactions", "alerts", "alert_events"):
        with op.batch_alter_table(table) as batch_op:
            _owner(batch_op, table)
    # Watchlist: a ticker is now unique per user, not globally. The new unique
    # constraint starts with `ticker`, so MySQL's foreign key on it stays indexed
    # while the old unique index is replaced by a plain one.
    with op.batch_alter_table("watchlist") as batch_op:
        _owner(batch_op, "watchlist")
        batch_op.create_unique_constraint("uq_watchlist_user_ticker", ["ticker", "user_id"])
    with op.batch_alter_table("watchlist") as batch_op:
        batch_op.drop_index("ix_watchlist_ticker")
        batch_op.create_index("ix_watchlist_ticker", ["ticker"], unique=False)


def downgrade() -> None:
    for table in OWNED:
        op.execute(f"DELETE FROM {table} WHERE user_id IS NOT NULL")
    with op.batch_alter_table("watchlist") as batch_op:
        batch_op.drop_index("ix_watchlist_ticker")
        batch_op.create_index("ix_watchlist_ticker", ["ticker"], unique=True)
    for table in OWNED:
        with op.batch_alter_table(table) as batch_op:
            if table == "watchlist":
                batch_op.drop_constraint("uq_watchlist_user_ticker", type_="unique")
            batch_op.drop_constraint(f"fk_{table}_user_id", type_="foreignkey")
            batch_op.drop_index(f"ix_{table}_user_id")
            batch_op.drop_column("user_id")

    op.drop_table("rating_state")
    op.create_table(
        "rating_state",
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("strength", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ticker"),
    )
    op.create_table(
        "preferences",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    owned = _prefs("user_preferences", sa.column("user_id"))
    _copy_preferences(owned, _prefs("preferences"), owned.c.user_id.is_(None))
    for table in ("user_preferences", "password_resets", "invites", "sessions", "users"):
        op.drop_table(table)
