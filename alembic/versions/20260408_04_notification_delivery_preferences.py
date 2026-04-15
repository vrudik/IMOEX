"""extend notification preferences for delivery policy

Revision ID: 20260408_04
Revises: 20260408_03
Create Date: 2026-04-08 18:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260408_04"
down_revision = "20260408_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_notification_preference",
        sa.Column(
            "subscribed_event_kinds_json",
            sa.String(length=512),
            nullable=False,
            server_default='["digest","signal_open","resolution","post_mortem"]',
        ),
    )
    op.add_column(
        "user_notification_preference",
        sa.Column(
            "suppress_during_quiet_hours",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_notification_preference", "suppress_during_quiet_hours")
    op.drop_column("user_notification_preference", "subscribed_event_kinds_json")
