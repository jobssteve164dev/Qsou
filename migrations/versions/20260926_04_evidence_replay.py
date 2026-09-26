"""Persist raw-evidence replay state and source parsing context."""

from alembic import op


revision = "20260926_04"
down_revision = "20260818_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE raw_objects "
        "ADD COLUMN IF NOT EXISTS request_context_json TEXT NOT NULL DEFAULT '{}'"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_replay_outbox (
            raw_object_id TEXT PRIMARY KEY REFERENCES raw_objects(raw_object_id),
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_replay_state "
        "ON evidence_replay_outbox (state, updated_at)"
    )
    op.execute(
        """
        INSERT INTO evidence_replay_outbox (
            raw_object_id, state, attempts, last_error, updated_at
        )
        SELECT r.raw_object_id,
               CASE WHEN EXISTS (
                   SELECT 1 FROM document_evidence d
                   WHERE d.raw_object_id = r.raw_object_id
               ) THEN 'parsed' ELSE 'pending' END,
               0, NULL, r.created_at
        FROM raw_objects r
        ON CONFLICT (raw_object_id) DO NOTHING
        """
    )


def downgrade() -> None:
    raise RuntimeError("原始证据回放状态不可破坏性降级；请使用备份恢复")
