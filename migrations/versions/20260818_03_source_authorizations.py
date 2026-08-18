"""Add an auditable source authorization lifecycle."""

import sqlalchemy as sa
from alembic import op


revision = "20260818_03"
down_revision = "20260818_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_authorizations",
        sa.Column("authorization_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text()),
        sa.Column("reference_url", sa.Text()),
        sa.Column("scope", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("decided_at", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("authorization_id"),
    )
    op.create_index(
        "idx_source_authorizations_source_time",
        "source_authorizations",
        ["source_id", sa.text("decided_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    raise RuntimeError("来源授权记录属于审计事实，请通过备份恢复而不是破坏性降级")
