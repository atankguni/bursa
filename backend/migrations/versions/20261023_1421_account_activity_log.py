"""Account activity log: sign-ins, password / 2FA changes and admin actions.

Revision ID: 20261023_142154
Revises: 20261023_080016
Create Date: 2026-10-23 14:21:54.343051+07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import db.types

revision: str = "20261023_142154"
down_revision: str | None = "20261023_080016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "account_created", "sign_in", "sign_in_failed", "session_revoked",
    "other_sessions_revoked", "password_changed", "password_reset", "reset_link_created",
    "two_factor_enabled", "two_factor_disabled", "two_factor_reset",
    "recovery_codes_regenerated", "trusted_devices_forgotten", "account_disabled",
    "account_enabled", "role_changed",
)


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("at", db.types.UTCDateTime(), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("device_hash", sa.String(length=64), nullable=True),
        sa.Column("new_device", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "kind IN (" + ", ".join(f"'{k}'" for k in KINDS) + ")",
            name=op.f("ck_security_events_kind_values"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_security_events_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    with op.batch_alter_table("security_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_security_events_at"), ["at"], unique=False)
        batch_op.create_index("ix_security_events_user_id_at", ["user_id", "at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("security_events", schema=None) as batch_op:
        batch_op.drop_index("ix_security_events_user_id_at")
        batch_op.drop_index(batch_op.f("ix_security_events_at"))
    op.drop_table("security_events")
