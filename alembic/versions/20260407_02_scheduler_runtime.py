"""add scheduler runtime persistence

Revision ID: 20260407_02
Revises: 20260407_01
Create Date: 2026-04-07 23:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260407_02"
down_revision = "20260407_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("command", sa.String(length=64), nullable=False),
        sa.Column("trigger_mode", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=2048), nullable=True),
        sa.Column("payload_blob", sa.String(length=8192), nullable=False),
        sa.Column("result_blob", sa.String(length=16384), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduler_run_run_id", "scheduler_run", ["run_id"], unique=True)
    op.create_index("ix_scheduler_run_job_id", "scheduler_run", ["job_id"], unique=False)
    op.create_index("ix_scheduler_run_trigger_mode", "scheduler_run", ["trigger_mode"], unique=False)
    op.create_index("ix_scheduler_run_idempotency_key", "scheduler_run", ["idempotency_key"], unique=True)
    op.create_index("ix_scheduler_run_status", "scheduler_run", ["status"], unique=False)
    op.create_index("ix_scheduler_run_scheduled_for", "scheduler_run", ["scheduled_for"], unique=False)
    op.create_index("ix_scheduler_run_started_at", "scheduler_run", ["started_at"], unique=False)
    op.create_index("ix_scheduler_run_finished_at", "scheduler_run", ["finished_at"], unique=False)
    op.create_index("ix_scheduler_run_created_at", "scheduler_run", ["created_at"], unique=False)

    op.create_table(
        "scheduler_lock",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lock_key", sa.String(length=256), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduler_lock_lock_key", "scheduler_lock", ["lock_key"], unique=True)
    op.create_index("ix_scheduler_lock_job_id", "scheduler_lock", ["job_id"], unique=False)
    op.create_index("ix_scheduler_lock_acquired_at", "scheduler_lock", ["acquired_at"], unique=False)
    op.create_index("ix_scheduler_lock_expires_at", "scheduler_lock", ["expires_at"], unique=False)
    op.create_index("ix_scheduler_lock_created_at", "scheduler_lock", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scheduler_lock_created_at", table_name="scheduler_lock")
    op.drop_index("ix_scheduler_lock_expires_at", table_name="scheduler_lock")
    op.drop_index("ix_scheduler_lock_acquired_at", table_name="scheduler_lock")
    op.drop_index("ix_scheduler_lock_job_id", table_name="scheduler_lock")
    op.drop_index("ix_scheduler_lock_lock_key", table_name="scheduler_lock")
    op.drop_table("scheduler_lock")

    op.drop_index("ix_scheduler_run_created_at", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_finished_at", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_started_at", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_scheduled_for", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_status", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_idempotency_key", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_trigger_mode", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_job_id", table_name="scheduler_run")
    op.drop_index("ix_scheduler_run_run_id", table_name="scheduler_run")
    op.drop_table("scheduler_run")
