"""add user notification preferences

Revision ID: 20260408_03
Revises: 20260407_02
Create Date: 2026-04-08 12:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260408_03"
down_revision = "20260407_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notification_preference",
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("default_root", sa.String(length=32), nullable=True),
        sa.Column("subscribed_roots_json", sa.String(length=2048), nullable=False),
        sa.Column("subscribed_horizons_json", sa.String(length=512), nullable=False),
        sa.Column("min_priority_score", sa.Integer(), nullable=False),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=True),
        sa.Column("digest_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.create_index(
        "ix_user_notification_preference_default_root",
        "user_notification_preference",
        ["default_root"],
        unique=False,
    )
    op.create_index(
        "ix_user_notification_preference_created_at",
        "user_notification_preference",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_notification_preference_updated_at",
        "user_notification_preference",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_notification_preference_updated_at", table_name="user_notification_preference")
    op.drop_index("ix_user_notification_preference_created_at", table_name="user_notification_preference")
    op.drop_index("ix_user_notification_preference_default_root", table_name="user_notification_preference")
    op.drop_table("user_notification_preference")
