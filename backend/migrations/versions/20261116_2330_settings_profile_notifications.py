"""Settings: alert emails with quiet hours, a portfolio benchmark and risk
limits per user; email changes confirmed by link; new activity-log entries
(name / email changes, portfolio cleared).

Revision ID: 20261116_233000
Revises: 20261113_203710
Create Date: 2026-11-16 23:30:00+07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import db.types

revision: str = "20261116_233000"
down_revision: str | None = "20261113_203710"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = "kind IN ('account_created', 'sign_in', 'sign_in_failed', 'session_revoked', 'other_sessions_revoked', 'password_changed', 'password_reset', 'reset_link_created', 'two_factor_enabled', 'two_factor_disabled', 'two_factor_reset', 'recovery_codes_regenerated', 'trusted_devices_forgotten', 'account_disabled', 'account_enabled', 'role_changed', 'session_unlocked')"
NEW_KINDS = "kind IN ('account_created', 'sign_in', 'sign_in_failed', 'session_revoked', 'other_sessions_revoked', 'password_changed', 'password_reset', 'reset_link_created', 'two_factor_enabled', 'two_factor_disabled', 'two_factor_reset', 'recovery_codes_regenerated', 'trusted_devices_forgotten', 'account_disabled', 'account_enabled', 'role_changed', 'session_unlocked', 'name_changed', 'email_change_requested', 'email_changed', 'portfolio_cleared')"


def upgrade() -> None:
    op.create_table(
        "email_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("new_email", sa.String(length=254), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("expires_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("used_at", db.types.UTCDateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_email_changes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_changes")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_changes_token_hash")),
    )
    with op.batch_alter_table("email_changes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_email_changes_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("user_settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("alert_emails", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("quiet_hours", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("risk_limits", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("benchmark", sa.String(length=12), nullable=True))
        batch_op.create_check_constraint(
            "benchmark_values", "benchmark IN ('COMPOSITE', 'LQ45', 'JII')"
        )

    with op.batch_alter_table("alert_events", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("email_pending", sa.Boolean(), server_default=sa.false(), nullable=False)
        )

    with op.batch_alter_table("security_events", schema=None) as batch_op:
        batch_op.drop_constraint("kind_values", type_="check")
        batch_op.create_check_constraint("kind_values", NEW_KINDS)


def downgrade() -> None:
    op.execute(
        "DELETE FROM security_events WHERE kind IN "
        "('name_changed', 'email_change_requested', 'email_changed', 'portfolio_cleared')"
    )
    with op.batch_alter_table("security_events", schema=None) as batch_op:
        batch_op.drop_constraint("kind_values", type_="check")
        batch_op.create_check_constraint("kind_values", OLD_KINDS)

    with op.batch_alter_table("alert_events", schema=None) as batch_op:
        batch_op.drop_column("email_pending")

    with op.batch_alter_table("user_settings", schema=None) as batch_op:
        batch_op.drop_constraint("benchmark_values", type_="check")
        batch_op.drop_column("benchmark")
        batch_op.drop_column("risk_limits")
        batch_op.drop_column("quiet_hours")
        batch_op.drop_column("alert_emails")

    with op.batch_alter_table("email_changes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_changes_user_id"))
    op.drop_table("email_changes")
