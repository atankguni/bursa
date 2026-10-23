"""API and worker coordination: worker status, scheduled jobs, worker tasks,
data versions; sign-in failures and assistant usage move out of process memory.

Revision ID: 20261023_080016
Revises: 20261023_073546
Create Date: 2026-10-23 08:00:16.051360+07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import db.types

revision: str = "20261023_080016"
down_revision: str | None = "20261023_073546"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_versions",
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("name IN ('scores')", name=op.f("ck_data_versions_name_values")),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_data_versions")),
    )
    op.create_table(
        "login_failures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("at", db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_failures")),
    )
    with op.batch_alter_table("login_failures", schema=None) as batch_op:
        batch_op.create_index("ix_login_failures_key_at", ["key", "at"], unique=False)

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("next_run_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("last_run_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("error", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_jobs")),
    )
    op.create_table(
        "worker_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("seen_at", db.types.UTCDateTime(), nullable=False),
        sa.Column("provider_stats", sa.JSON(), nullable=False),
        sa.Column("last_price_sync_at", db.types.UTCDateTime(), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_worker_status_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_status")),
    )
    op.create_table(
        "worker_tasks",
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("request", sa.JSON(), nullable=True),
        sa.Column("requested_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("running", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("done", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("started_at", db.types.UTCDateTime(), nullable=True),
        sa.Column("finished_at", db.types.UTCDateTime(), nullable=True),
        sa.CheckConstraint("mode IN ('batch', 'all')", name=op.f("ck_worker_tasks_mode_values")),
        sa.CheckConstraint(
            "name IN ('fundamentals_sync')", name=op.f("ck_worker_tasks_name_values")
        ),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_worker_tasks")),
    )
    op.create_table(
        "assistant_usage",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("questions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assistant_usage_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "day", name=op.f("pk_assistant_usage")),
    )


def downgrade() -> None:
    op.drop_table("assistant_usage")
    op.drop_table("worker_tasks")
    op.drop_table("worker_status")
    op.drop_table("scheduled_jobs")
    with op.batch_alter_table("login_failures", schema=None) as batch_op:
        batch_op.drop_index("ix_login_failures_key_at")

    op.drop_table("login_failures")
    op.drop_table("data_versions")
