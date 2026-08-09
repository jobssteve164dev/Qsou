"""Adopt the QSou PostgreSQL catalog as the only runtime schema."""

from alembic import context, op

from qsou_data.schema import metadata


revision = "20260809_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(
        op.get_bind(),
        checkfirst=not context.is_offline_mode(),
    )


def downgrade() -> None:
    raise RuntimeError("QSou PostgreSQL 基线不支持破坏性整体降级；请使用备份恢复")
