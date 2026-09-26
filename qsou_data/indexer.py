"""Continuously project PostgreSQL standard documents into Elasticsearch."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

from .indexer_state import write_indexer_state
from .migration_state import wait_for_migrations
from .processing import BaselineDocumentProcessor, run_processing_batch
from .search_index import ElasticsearchIndex, IndexBatchError
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


def _reconcile_all(
    store: DataAssetStore,
    index: ElasticsearchIndex,
    *,
    reason: str,
) -> tuple[int, int]:
    generation = uuid.uuid4().hex
    try:
        reconciled_ids = index.index_documents(
            store.documents_for_index(),
            projection_generation=generation,
        )
    except IndexBatchError as exc:
        if exc.indexed_ids:
            store.mark_indexed(exc.indexed_ids)
            index.refresh()
        if exc.failed_ids:
            store.mark_failed(
                exc.failed_ids,
                f"indexing: {str(exc)[:980]}",
            )
        if exc.retryable_ids:
            store.record_index_failure(
                exc.retryable_ids,
                f"indexing: {str(exc)[:980]}",
            )
        raise
    removed = index.delete_stale(generation)
    index.refresh()
    store.mark_indexed(reconciled_ids)
    _event(
        "reconciled",
        documents=len(reconciled_ids),
        removed=removed,
        reason=reason,
    )
    return len(reconciled_ids), removed


def _projection_checkpoint(
    store: DataAssetStore,
    index: ElasticsearchIndex,
) -> dict[str, int | bool]:
    # A collector may commit another document between reading the two backends.
    # Only a checkpoint with no outstanding PostgreSQL rows is comparable.
    count_projectable = getattr(store, "projectable_active_document_count", None)
    if count_projectable is None:
        count_projectable = store.active_document_count
    active_documents_before = count_projectable()
    pending_before_count = len(store.pending_documents_for_index(1))
    indexed_active_documents = index.active_document_count()
    active_documents = count_projectable()
    pending_after_count = len(store.pending_documents_for_index(1))
    return {
        "active_documents": active_documents,
        "indexed_active_documents": indexed_active_documents,
        "pending_documents": pending_after_count,
        "converged": (
            active_documents_before == active_documents
            and pending_before_count == 0
            and pending_after_count == 0
        ),
    }


def run_cycle(
    store: DataAssetStore,
    index: ElasticsearchIndex,
    *,
    last_reconcile: float,
    reconcile_seconds: int,
    batch_size: int,
    processor: BaselineDocumentProcessor | None = None,
    now: float | None = None,
) -> tuple[float, dict[str, int | bool]]:
    current = time.monotonic() if now is None else now
    reconciled = 0
    processing = {
        "claimed": 0,
        "processed": 0,
        "filtered": 0,
        "processing_failed": 0,
    }
    if processor is not None:
        processing = run_processing_batch(
            store,
            processor,
            batch_size=batch_size,
        )
    index.ensure_ready()
    if current - last_reconcile >= reconcile_seconds:
        reconciled, _ = _reconcile_all(
            store,
            index,
            reason="scheduled",
        )
        last_reconcile = current

    pending = store.pending_documents_for_index(batch_size)
    indexed = 0
    if pending:
        pending_ids = [
            str(document.get("content_version_id") or document.get("id") or "")
            for document in pending
        ]
        try:
            ids = index.index_documents(pending)
        except IndexBatchError as exc:
            if exc.indexed_ids:
                store.mark_indexed(exc.indexed_ids)
                index.refresh()
            failed_ids = exc.failed_ids or [
                item
                for item in pending_ids
                if item not in exc.indexed_ids and item not in exc.retryable_ids
            ]
            if failed_ids:
                store.mark_failed(
                    failed_ids,
                    f"indexing: {str(exc)[:980]}",
                )
            if exc.retryable_ids:
                store.record_index_failure(
                    exc.retryable_ids,
                    f"indexing: {str(exc)[:980]}",
                )
            raise
        except Exception as exc:
            store.record_index_failure(
                pending_ids,
                f"indexing: {str(exc)[:980]}",
            )
            raise
        store.mark_indexed(ids)
        index.refresh()
        indexed = len(ids)
        _event("indexed", documents=indexed)
    checkpoint = _projection_checkpoint(store, index)
    if (
        checkpoint["converged"]
        and checkpoint["active_documents"]
        != checkpoint["indexed_active_documents"]
    ):
        reconciled, _ = _reconcile_all(
            store,
            index,
            reason="consistency_repair",
        )
        last_reconcile = current
        checkpoint = _projection_checkpoint(store, index)
    if (
        checkpoint["converged"]
        and checkpoint["active_documents"]
        != checkpoint["indexed_active_documents"]
    ):
        raise RuntimeError(
            "Elasticsearch 活动文档计数与 PostgreSQL 不一致: "
            f"postgres={checkpoint['active_documents']}, "
            f"elasticsearch={checkpoint['indexed_active_documents']}"
        )
    result = {
        "reconciled": reconciled,
        "indexed": indexed,
        **checkpoint,
    }
    if processor is not None:
        result.update(processing)
    return last_reconcile, result


def main() -> int:
    poll_seconds = max(1, int(os.getenv("QSOU_INDEXER_POLL_SECONDS", "5")))
    reconcile_seconds = max(60, int(os.getenv("QSOU_INDEXER_RECONCILE_SECONDS", "3600")))
    batch_size = max(1, min(int(os.getenv("QSOU_INDEXER_BATCH_SIZE", "100")), 1000))
    store = DataAssetStore()
    index = ElasticsearchIndex()
    processor = BaselineDocumentProcessor()
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
                    processor=processor,
                )
                write_indexer_state("healthy", **result)
            except Exception as exc:
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
