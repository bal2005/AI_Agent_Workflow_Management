"""add trigger_config to schedules and trigger_logs table

Revision ID: 009
Revises: 008
Create Date: 2026-04-01
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add trigger_config JSON column to schedules
    op.add_column("schedules", sa.Column("trigger_config", sa.JSON(), nullable=True))

    # Trigger event log table
    op.create_table(
        "trigger_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),   # created|modified|deleted|moved
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("debounced", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("workflow_fired", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trigger_logs_schedule_id", "trigger_logs", ["schedule_id"])
    op.create_index("ix_trigger_logs_triggered_at", "trigger_logs", ["triggered_at"])


def downgrade() -> None:
    op.drop_index("ix_trigger_logs_triggered_at", table_name="trigger_logs")
    op.drop_index("ix_trigger_logs_schedule_id", table_name="trigger_logs")
    op.drop_table("trigger_logs")
    op.drop_column("schedules", "trigger_config")
