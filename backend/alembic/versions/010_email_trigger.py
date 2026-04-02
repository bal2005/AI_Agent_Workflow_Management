"""add email_trigger_state table

Revision ID: 010
Revises: 009
Create Date: 2026-04-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_trigger_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(),
                  sa.ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False),
        # IMAP UID is a string (some servers use non-numeric UIDs)
        sa.Column("message_uid", sa.String(200), nullable=False),
        sa.Column("sender",  sa.String(500), nullable=True),
        sa.Column("subject", sa.String(1000), nullable=True),
        sa.Column("seen_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "message_uid",
                            name="uq_email_trigger_state_schedule_uid"),
    )
    op.create_index("ix_email_trigger_state_schedule_id",
                    "email_trigger_state", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_email_trigger_state_schedule_id",
                  table_name="email_trigger_state")
    op.drop_table("email_trigger_state")
