"""add skip-next delivery controls

Revision ID: 20260408_05
Revises: 20260408_04
Create Date: 2026-04-08 22:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260408_05"
down_revision = "20260408_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_notification_preference",
        sa.Column(
            "skip_next_event_kinds_json",
            sa.String(length=512),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_notification_preference", "skip_next_event_kinds_json")
