"""Continuously project PostgreSQL standard documents into Elasticsearch."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

from .indexer_state import write_indexer_state
from .migration_state import wait_for_migrations
from .search_index import ElasticsearchIndex
from .store import DataAssetStore


def _event(event: str, **details) -> None:
    print(
        "QSOU_INDEXER_EVENT="
        + json.dumps(
            {
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **details,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def run_cycle(
    store: DataAssetStore,
    index: ElasticsearchIndex,
    *,
    last_reconcile: float,
    reconcile_seconds: int,
    batch_size: int,
    now: float | None = None,
) -> tuple[float, dict[str, int]]:
    current = time.monotonic() if now is None else now
    reconciled = 0
    index.ensure_ready()
    if current - last_reconcile >= reconcile_seconds:
        generation = uuid.uuid4().hex
        reconciled_ids = index.index_documents(
            store.documents_for_index(),
            projection_generation=generation,
        )
        removed = index.delete_stale(generation)
        index.refresh()
        reconciled = len(reconciled_ids)
        store.mark_indexed(reconciled_ids)
        last_reconcile = current
        _event("reconciled", documents=reconciled, removed=removed)

    pending = store.pending_documents_for_index(batch_size)
    indexed = 0
    if pending:
        ids = index.index_documents(pending)
        store.mark_indexed(ids)
        index.refresh()
        indexed = len(ids)
        _event("indexed", documents=indexed)
    active_documents = store.active_document_count()
    indexed_active_documents = index.active_document_count()
    if active_documents != indexed_active_documents:
        raise RuntimeError(
            "Elasticsearch 活动文档计数与 PostgreSQL 不一致: "
            f"postgres={active_documents}, elasticsearch={indexed_active_documents}"
        )
    return last_reconcile, {
        "reconciled": reconciled,
        "indexed": indexed,
        "active_documents": active_documents,
        "indexed_active_documents": indexed_active_documents,
    }


def main() -> int:
    poll_seconds = max(1, int(os.getenv("QSOU_INDEXER_POLL_SECONDS", "5")))
    reconcile_seconds = max(60, int(os.getenv("QSOU_INDEXER_RECONCILE_SECONDS", "3600")))
    batch_size = max(1, min(int(os.getenv("QSOU_INDEXER_BATCH_SIZE", "100")), 1000))
    store = DataAssetStore()
    index = ElasticsearchIndex()
    last_reconcile = 0.0
    try:
        wait_for_migrations(
            store,
            on_wait=lambda state: write_indexer_state(
                "waiting_for_migration",
                migration=state,
            ),
        )
        while True:
            try:
                last_reconcile, result = run_cycle(
                    store,
                    index,
                    last_reconcile=last_reconcile,
                    reconcile_seconds=reconcile_seconds,
                    batch_size=batch_size,
                )
                write_indexer_state("healthy", **result)
            except Exception as exc:
                pending = store.pending_documents_for_index(batch_size)
                pending_ids = [
                    str(document.get("content_version_id") or document.get("id") or "")
                    for document in pending
                ]
                store.mark_failed(pending_ids, str(exc)[:1000])
                write_indexer_state(
                    "failed",
                    error_type=type(exc).__name__,
                    error=str(exc)[:1000],
                )
                _event("failed", error_type=type(exc).__name__, error=str(exc)[:1000])
            time.sleep(poll_seconds)
    finally:
        index.close()


if __name__ == "__main__":
    raise SystemExit(main())
