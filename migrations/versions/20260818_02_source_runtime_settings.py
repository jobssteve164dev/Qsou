"""Persist per-source collection switches and schedules."""

import sqlalchemy as sa
from alembic import op


revision = "20260818_02"
down_revision = "20260809_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_runtime_settings",
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule", sa.Text(), nullable=False),
        sa.Column("max_details_per_run", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("source_id"),
    )


def downgrade() -> None:
    raise RuntimeError("来源采集设置包含运行治理状态，请通过备份恢复而不是破坏性降级")
