"""Inactivity lock: per-session activity and lock state, the lock setting, and the
"session_unlocked" activity-log entry.

Revision ID: 20261023_214739
Revises: 20261023_142154
Create Date: 2026-10-23 21:47:39.756887+07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import db.types

revision: str = "20261023_214739"
down_revision: str | None = "20261023_142154"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "account_created", "sign_in", "sign_in_failed", "session_revoked",
    "other_sessions_revoked", "password_changed", "password_reset", "reset_link_created",
    "two_factor_enabled", "two_factor_disabled", "two_factor_reset",
    "recovery_codes_regenerated", "trusted_devices_forgotten", "account_disabled",
    "account_enabled", "role_changed",
)
NEW_KINDS = (*KINDS, "session_unlocked")
KIND_CHECK = "kind_values"  # named ck_security_events_kind_values by the convention


def _kind_check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("active_at", db.types.UTCDateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("locked", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("unlock_failures", sa.Integer(), server_default="0", nullable=False)
        )
    # Existing sessions were last used when last seen (they lock if idle since).
    op.execute("UPDATE sessions SET active_at = last_seen_at")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column("active_at", existing_type=db.types.UTCDateTime(), nullable=False)

    with op.batch_alter_table("user_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lock_minutes", sa.Integer(), nullable=True))

    with op.batch_alter_table("security_events", schema=None) as batch_op:
        batch_op.drop_constraint(KIND_CHECK, type_="check")
        batch_op.create_check_constraint(KIND_CHECK, _kind_check(NEW_KINDS))


def downgrade() -> None:
    op.execute("DELETE FROM security_events WHERE kind = 'session_unlocked'")
    with op.batch_alter_table("security_events", schema=None) as batch_op:
        batch_op.drop_constraint(KIND_CHECK, type_="check")
        batch_op.create_check_constraint(KIND_CHECK, _kind_check(KINDS))

    with op.batch_alter_table("user_settings", schema=None) as batch_op:
        batch_op.drop_column("lock_minutes")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("unlock_failures")
        batch_op.drop_column("locked")
        batch_op.drop_column("active_at")
