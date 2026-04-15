"""add notification delivery activity log

Revision ID: 20260409_06
Revises: 20260408_05
Create Date: 2026-04-09 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260409_06"
down_revision = "20260408_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_delivery_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column("delivery_source", sa.String(length=32), nullable=True),
        sa.Column("root_code", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=2048), nullable=False),
        sa.Column("signal_ids_json", sa.String(length=2048), nullable=False, server_default="[]"),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id"),
    )
    op.create_index(op.f("ix_notification_delivery_event_activity_id"), "notification_delivery_event", ["activity_id"], unique=True)
    op.create_index(op.f("ix_notification_delivery_event_profile_id"), "notification_delivery_event", ["profile_id"], unique=False)
    op.create_index(op.f("ix_notification_delivery_event_action"), "notification_delivery_event", ["action"], unique=False)
    op.create_index(op.f("ix_notification_delivery_event_event_kind"), "notification_delivery_event", ["event_kind"], unique=False)
    op.create_index(op.f("ix_notification_delivery_event_root_code"), "notification_delivery_event", ["root_code"], unique=False)
    op.create_index(op.f("ix_notification_delivery_event_status"), "notification_delivery_event", ["status"], unique=False)
    op.create_index(op.f("ix_notification_delivery_event_created_at"), "notification_delivery_event", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_delivery_event_created_at"), table_name="notification_delivery_event")
    op.drop_index(op.f("ix_notification_delivery_event_status"), table_name="notification_delivery_event")
    op.drop_index(op.f("ix_notification_delivery_event_root_code"), table_name="notification_delivery_event")
    op.drop_index(op.f("ix_notification_delivery_event_event_kind"), table_name="notification_delivery_event")
    op.drop_index(op.f("ix_notification_delivery_event_action"), table_name="notification_delivery_event")
    op.drop_index(op.f("ix_notification_delivery_event_profile_id"), table_name="notification_delivery_event")
    op.drop_index(op.f("ix_notification_delivery_event_activity_id"), table_name="notification_delivery_event")
    op.drop_table("notification_delivery_event")
