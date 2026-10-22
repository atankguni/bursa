"""Two-factor authentication: methods on users, recovery codes, pending
challenges and remembered devices.

Revision ID: 20261017_225100
Revises: 20261017_222700
Create Date: 2026-10-17 22:51
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_225100"
down_revision: str | None = "20261017_222700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], name=f"fk_{table}_user_id", ondelete="CASCADE"
    )


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("mfa_email", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("totp_secret", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("totp_pending", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("totp_last_step", sa.BigInteger(), nullable=True))

    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        _user_fk("recovery_codes"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_codes_user_id", "recovery_codes", ["user_id"], unique=False)

    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("email_code_hash", sa.String(length=64), nullable=True),
        sa.Column("email_sent_at", sa.DateTime(), nullable=True),
        _user_fk("mfa_challenges"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_mfa_challenges_token_hash"),
    )
    op.create_index("ix_mfa_challenges_user_id", "mfa_challenges", ["user_id"], unique=False)
    op.create_index(
        "ix_mfa_challenges_expires_at", "mfa_challenges", ["expires_at"], unique=False
    )

    op.create_table(
        "trusted_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        _user_fk("trusted_devices"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_trusted_devices_token_hash"),
    )
    op.create_index("ix_trusted_devices_user_id", "trusted_devices", ["user_id"], unique=False)
    op.create_index(
        "ix_trusted_devices_expires_at", "trusted_devices", ["expires_at"], unique=False
    )


def downgrade() -> None:
    for table in ("trusted_devices", "mfa_challenges", "recovery_codes"):
        op.drop_table(table)
    with op.batch_alter_table("users") as batch_op:
        for column in ("totp_last_step", "totp_pending", "totp_secret", "mfa_email"):
            batch_op.drop_column(column)
