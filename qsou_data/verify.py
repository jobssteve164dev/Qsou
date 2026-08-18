"""Catalog and immutable evidence verification for cutover and restore acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Sequence

from .catalog import normalize_catalog_value
from .schema import metadata
from .store import DataAssetError, DataAssetStore


BATCH_SIZE = 100
VERIFICATION_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("raw_objects", ("raw_object_id",)),
    ("standard_documents", ("content_version_id",)),
    ("document_evidence", ("content_version_id", "raw_object_id")),
    ("processing_outbox", ("content_version_id",)),
    ("adapter_runs", ("run_id",)),
    ("source_cursors", ("source_id",)),
    ("source_runtime_settings", ("source_id",)),
    ("source_authorizations", ("authorization_id",)),
    ("adapter_run_requests", ("request_id",)),
)


def _update_digest(
    digest,
    rows: Iterable[Mapping[str, Any]],
    columns: Sequence[str],
) -> int:
    count = 0
    for row in rows:
        encoded = json.dumps(
            [normalize_catalog_value(row[column]) for column in columns],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    return count


def _cursor_digest(cursor, columns: Sequence[str]) -> tuple[int, str]:
    count = 0
    digest = hashlib.sha256()
    while True:
        rows = cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        count += _update_digest(digest, rows, columns)
    return count, digest.hexdigest()


def verify_storage(store: DataAssetStore, *, require_backup: bool = False) -> Dict[str, Any]:
    table_counts: Dict[str, int] = {}
    table_digests: Dict[str, str] = {}
    has_backup = bool(getattr(store.object_store, "backup_bucket", None))
    if require_backup and not has_backup:
        raise DataAssetError("生产验收要求备份桶，但当前对象存储未配置备份桶")

    with store._connection() as connection:
        for table, keys in VERIFICATION_TABLES:
            columns = [column.name for column in metadata.tables[table].columns]
            cursor = connection.execute(
                f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(keys)}"
            )
            count, digest = _cursor_digest(cursor, columns)
            table_counts[table] = count
            table_digests[table] = digest

        orphan_queries = {
            "documents_without_raw": """
                SELECT COUNT(*) AS count FROM standard_documents d
                LEFT JOIN raw_objects r ON r.raw_object_id = d.raw_object_id
                WHERE r.raw_object_id IS NULL
            """,
            "evidence_without_document": """
                SELECT COUNT(*) AS count FROM document_evidence e
                LEFT JOIN standard_documents d ON d.content_version_id = e.content_version_id
                WHERE d.content_version_id IS NULL
            """,
            "evidence_without_raw": """
                SELECT COUNT(*) AS count FROM document_evidence e
                LEFT JOIN raw_objects r ON r.raw_object_id = e.raw_object_id
                WHERE r.raw_object_id IS NULL
            """,
            "outbox_without_document": """
                SELECT COUNT(*) AS count FROM processing_outbox o
                LEFT JOIN standard_documents d ON d.content_version_id = o.content_version_id
                WHERE d.content_version_id IS NULL
            """,
        }
        orphans = {
            name: int(connection.execute(query).fetchone()["count"])
            for name, query in orphan_queries.items()
        }
        if any(orphans.values()):
            raise DataAssetError(f"目录库存在孤儿关系: {orphans}")

        raw_cursor = connection.execute(
            """
            SELECT raw_object_id, body_path, content_hash
            FROM raw_objects ORDER BY raw_object_id
            """
        )
        migrations = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]
        object_count = 0
        object_bytes = 0
        while True:
            raw_rows = raw_cursor.fetchmany(BATCH_SIZE)
            if not raw_rows:
                break
            for row in raw_rows:
                payload = store.object_store.get_primary_bytes(row["body_path"])
                checksum = hashlib.sha256(payload).hexdigest()
                if checksum != row["content_hash"]:
                    raise DataAssetError(f"主对象哈希不一致: {row['raw_object_id']}")
                if has_backup:
                    backup = store.object_store.get_backup_bytes(row["body_path"])
                    if hashlib.sha256(backup).hexdigest() != checksum:
                        raise DataAssetError(f"备份对象哈希不一致: {row['raw_object_id']}")
                object_count += 1
                object_bytes += len(payload)

    catalog_digest = hashlib.sha256(
        json.dumps(
            table_digests,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "status": "verified",
        "catalog_backend": store.catalog.backend,
        "object_backend": store.object_store.backend,
        "backup_verified": has_backup,
        "table_counts": table_counts,
        "catalog_digest": catalog_digest,
        "orphans": orphans,
        "object_count": object_count,
        "object_bytes": object_bytes,
        "schema_migrations": migrations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="QSou 目录库与对象存储一致性验收")
    parser.add_argument("--require-backup", action="store_true")
    args = parser.parse_args()
    result = verify_storage(DataAssetStore(), require_backup=args.require_backup)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
