"""add workflow_json column to schedules

Revision ID: 008
Revises: 007
Create Date: 2026-03-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Stores the visual workflow graph as a JSON blob.
    # Shape: { "nodes": [ { "id", "type", "label", "description", "taskId", "triggerType" }, ... ] }
    op.add_column(
        "schedules",
        sa.Column("workflow_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schedules", "workflow_json")
