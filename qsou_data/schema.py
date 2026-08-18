"""Authoritative PostgreSQL catalog schema."""

from __future__ import annotations

import sqlalchemy as sa


metadata = sa.MetaData()

raw_objects = sa.Table(
    "raw_objects",
    metadata,
    sa.Column("raw_object_id", sa.Text, primary_key=True),
    sa.Column("source_id", sa.Text, nullable=False),
    sa.Column("url", sa.Text, nullable=False),
    sa.Column("status_code", sa.Integer, nullable=False),
    sa.Column("content_hash", sa.Text, nullable=False),
    sa.Column("body_path", sa.Text, nullable=False),
    sa.Column("content_type", sa.Text, nullable=False),
    sa.Column("encoding", sa.Text),
    sa.Column("response_headers_json", sa.Text, nullable=False),
    sa.Column("collector", sa.Text, nullable=False),
    sa.Column("first_fetched_at", sa.Text, nullable=False),
    sa.Column("last_fetched_at", sa.Text, nullable=False),
    sa.Column("fetch_count", sa.Integer, nullable=False, server_default="1"),
    sa.Column("created_at", sa.Text, nullable=False),
)
sa.Index("idx_raw_source_time", raw_objects.c.source_id, raw_objects.c.first_fetched_at.desc())

standard_documents = sa.Table(
    "standard_documents",
    metadata,
    sa.Column("content_version_id", sa.Text, primary_key=True),
    sa.Column("canonical_document_id", sa.Text, nullable=False),
    sa.Column("source_document_id", sa.Text, nullable=False),
    sa.Column("raw_object_id", sa.Text, sa.ForeignKey("raw_objects.raw_object_id"), nullable=False),
    sa.Column("source_id", sa.Text, nullable=False),
    sa.Column("document_type", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("url", sa.Text, nullable=False),
    sa.Column("content_hash", sa.Text, nullable=False),
    sa.Column("source_published_at", sa.Text),
    sa.Column("first_seen_at", sa.Text, nullable=False),
    sa.Column("fetched_at", sa.Text, nullable=False),
    sa.Column("processed_at", sa.Text),
    sa.Column("indexed_at", sa.Text),
    sa.Column("superseded_at", sa.Text),
    sa.Column("parser_version", sa.Text, nullable=False),
    sa.Column("document_json", sa.Text, nullable=False),
    sa.Column("active", sa.Integer, nullable=False, server_default="1"),
    sa.Column("created_at", sa.Text, nullable=False),
)
sa.Index(
    "idx_docs_canonical",
    standard_documents.c.canonical_document_id,
    standard_documents.c.first_seen_at,
)
sa.Index(
    "idx_docs_source_time",
    standard_documents.c.source_id,
    standard_documents.c.first_seen_at.desc(),
)

document_evidence = sa.Table(
    "document_evidence",
    metadata,
    sa.Column(
        "content_version_id",
        sa.Text,
        sa.ForeignKey("standard_documents.content_version_id"),
        primary_key=True,
    ),
    sa.Column(
        "raw_object_id",
        sa.Text,
        sa.ForeignKey("raw_objects.raw_object_id"),
        primary_key=True,
    ),
    sa.Column("observed_at", sa.Text, nullable=False),
)

processing_outbox = sa.Table(
    "processing_outbox",
    metadata,
    sa.Column(
        "content_version_id",
        sa.Text,
        sa.ForeignKey("standard_documents.content_version_id"),
        primary_key=True,
    ),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("task_id", sa.Text),
    sa.Column("last_error", sa.Text),
    sa.Column("updated_at", sa.Text, nullable=False),
)
sa.Index("idx_outbox_state", processing_outbox.c.state, processing_outbox.c.updated_at)

adapter_runs = sa.Table(
    "adapter_runs",
    metadata,
    sa.Column("run_id", sa.Text, primary_key=True),
    sa.Column("source_id", sa.Text, nullable=False),
    sa.Column("adapter_id", sa.Text, nullable=False),
    sa.Column("adapter_version", sa.Text, nullable=False),
    sa.Column("trigger", sa.Text, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("started_at", sa.Text, nullable=False),
    sa.Column("finished_at", sa.Text),
    sa.Column("entrypoints_total", sa.Integer, nullable=False, server_default="0"),
    sa.Column("entrypoints_succeeded", sa.Integer, nullable=False, server_default="0"),
    sa.Column("detail_discovered", sa.Integer, nullable=False, server_default="0"),
    sa.Column("detail_fetched", sa.Integer, nullable=False, server_default="0"),
    sa.Column("documents_emitted", sa.Integer, nullable=False, server_default="0"),
    sa.Column("evidence_archived", sa.Integer, nullable=False, server_default="0"),
    sa.Column("failures", sa.Integer, nullable=False, server_default="0"),
    sa.Column("cursor_before_json", sa.Text),
    sa.Column("cursor_after_json", sa.Text),
    sa.Column("error_summary_json", sa.Text),
    sa.Column("metrics_json", sa.Text, nullable=False, server_default="{}"),
)
sa.Index("idx_adapter_runs_source_time", adapter_runs.c.source_id, adapter_runs.c.started_at.desc())

source_cursors = sa.Table(
    "source_cursors",
    metadata,
    sa.Column("source_id", sa.Text, primary_key=True),
    sa.Column("adapter_id", sa.Text, nullable=False),
    sa.Column("adapter_version", sa.Text, nullable=False),
    sa.Column("cursor_json", sa.Text, nullable=False),
    sa.Column("updated_at", sa.Text, nullable=False),
)

source_runtime_settings = sa.Table(
    "source_runtime_settings",
    metadata,
    sa.Column("source_id", sa.Text, primary_key=True),
    sa.Column("enabled", sa.Boolean, nullable=False),
    sa.Column("schedule", sa.Text, nullable=False),
    sa.Column("max_details_per_run", sa.Integer, nullable=False),
    sa.Column("updated_at", sa.Text, nullable=False),
    sa.Column("updated_by", sa.Text, nullable=False),
)

adapter_run_requests = sa.Table(
    "adapter_run_requests",
    metadata,
    sa.Column("request_id", sa.Text, primary_key=True),
    sa.Column("source_id", sa.Text, nullable=False),
    sa.Column("requested_by", sa.Text, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("requested_at", sa.Text, nullable=False),
    sa.Column("claimed_at", sa.Text),
    sa.Column("finished_at", sa.Text),
    sa.Column("run_id", sa.Text),
    sa.Column("result_state", sa.Text),
    sa.Column("error", sa.Text),
)
sa.Index(
    "idx_adapter_requests_state_time",
    adapter_run_requests.c.state,
    adapter_run_requests.c.requested_at,
)
sa.Index(
    "idx_adapter_requests_one_active",
    adapter_run_requests.c.source_id,
    unique=True,
    postgresql_where=adapter_run_requests.c.state.in_(["queued", "running"]),
)

schema_migrations = sa.Table(
    "schema_migrations",
    metadata,
    sa.Column("version", sa.Text, primary_key=True),
    sa.Column("applied_at", sa.Text, nullable=False),
    sa.Column("details_json", sa.Text, nullable=False),
)

migration_audits = sa.Table(
    "migration_audits",
    metadata,
    sa.Column("migration_id", sa.Text, primary_key=True),
    sa.Column("source_backend", sa.Text, nullable=False),
    sa.Column("target_backend", sa.Text, nullable=False),
    sa.Column("phase", sa.Text, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("started_at", sa.Text, nullable=False),
    sa.Column("finished_at", sa.Text),
    sa.Column("table_counts_json", sa.Text),
    sa.Column("catalog_digest", sa.Text),
    sa.Column("object_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("object_bytes", sa.Integer, nullable=False, server_default="0"),
    sa.Column("error", sa.Text),
)
