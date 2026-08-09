#!/usr/bin/env python3
"""One-time, read-only import of the retired QSou SQLite catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qsou_data.catalog import Catalog, normalize_catalog_value
from qsou_data.migration_state import SQLITE_IMPORT_VERSION
from qsou_data.schema import metadata


MIGRATION_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("raw_objects", ("raw_object_id",)),
    ("standard_documents", ("content_version_id",)),
    ("document_evidence", ("content_version_id", "raw_object_id")),
    ("processing_outbox", ("content_version_id",)),
    ("adapter_runs", ("run_id",)),
    ("source_cursors", ("source_id",)),
    ("adapter_run_requests", ("request_id",)),
)
MIGRATION_VERSION = SQLITE_IMPORT_VERSION
BATCH_SIZE = 100
ADVISORY_LOCK_ID = 781_937_611


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _update_digest(
    digest,
    rows: Iterable[Mapping[str, Any]],
    columns: Sequence[str],
) -> int:
    count = 0
    for row in rows:
        encoded = _json(
            [normalize_catalog_value(row[column]) for column in columns]
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


def _source_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    columns = [str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")]
    target = metadata.tables[table]
    unknown = sorted(set(columns) - set(target.columns.keys()))
    if unknown:
        raise RuntimeError(f"{table} 包含目标 schema 未声明字段: {unknown}")
    return columns


def _upsert_sql(table: str, columns: Sequence[str], keys: Sequence[str]) -> str:
    values = ", ".join("%s" for _ in columns)
    updates = [column for column in columns if column not in keys]
    action = (
        "DO UPDATE SET "
        + ", ".join(f"{column} = excluded.{column}" for column in updates)
        if updates
        else "DO NOTHING"
    )
    return (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values}) "
        f"ON CONFLICT ({', '.join(keys)}) {action}"
    )


def _source_file_candidates(sqlite_path: Path) -> list[str]:
    return [
        str(path)
        for path in (
            sqlite_path,
            Path(f"{sqlite_path}-wal"),
            Path(f"{sqlite_path}-shm"),
        )
        if path.exists()
    ]


def migrate(sqlite_path: Path, data_root: Path) -> dict[str, Any]:
    sqlite_path = sqlite_path.resolve()
    if not sqlite_path.is_file():
        raise RuntimeError(f"SQLite 迁移源不存在: {sqlite_path}")

    source = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True, timeout=30)
    source.row_factory = sqlite3.Row
    try:
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite 完整性检查失败: {integrity}")
        source.execute("BEGIN")
        source_version = int(source.execute("PRAGMA data_version").fetchone()[0])
        table_counts: dict[str, dict[str, int]] = {}
        table_digests: dict[str, str] = {}
        normalized_nul_bytes = 0

        catalog = Catalog(data_root)
        with catalog.connection() as target:
            target.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))
            for table, keys in MIGRATION_TABLES:
                columns = _source_columns(source, table)
                if not columns:
                    raise RuntimeError(f"SQLite 迁移源缺少表: {table}")
                source_cursor = source.execute(
                    f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(keys)}"
                )
                source_count = 0
                source_digest = hashlib.sha256()
                while True:
                    rows = source_cursor.fetchmany(BATCH_SIZE)
                    if not rows:
                        break
                    values = []
                    for row in rows:
                        normalized = []
                        for column in columns:
                            value = row[column]
                            if isinstance(value, str):
                                normalized_nul_bytes += value.count("\x00")
                            normalized.append(normalize_catalog_value(value))
                        values.append(tuple(normalized))
                    target.executemany(_upsert_sql(table, columns, keys), values)
                    source_count += _update_digest(source_digest, rows, columns)

                target_cursor = target.execute(
                    f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(keys)}"
                )
                target_count, target_digest = _cursor_digest(target_cursor, columns)
                digest = source_digest.hexdigest()
                if source_count != target_count or digest != target_digest:
                    raise RuntimeError(
                        f"{table} 迁移校验失败: "
                        f"source={source_count}/{digest}, target={target_count}/{target_digest}"
                    )
                table_counts[table] = {"source": source_count, "target": target_count}
                table_digests[table] = digest

            if int(source.execute("PRAGMA data_version").fetchone()[0]) != source_version:
                raise RuntimeError("迁移期间 SQLite 仍发生写入")

            catalog_digest = hashlib.sha256(_json(table_digests).encode("utf-8")).hexdigest()
            migration_id = uuid.uuid4().hex
            details = {
                "table_counts": table_counts,
                "catalog_digest": catalog_digest,
                "text_nul_bytes_normalized": normalized_nul_bytes,
            }
            target.execute(
                """
                INSERT INTO schema_migrations (version, applied_at, details_json)
                VALUES (%s, CURRENT_TIMESTAMP::text, %s)
                ON CONFLICT (version) DO UPDATE SET
                    applied_at = excluded.applied_at,
                    details_json = excluded.details_json
                """,
                (MIGRATION_VERSION, _json(details)),
            )
            target.execute(
                """
                INSERT INTO migration_audits (
                    migration_id, source_backend, target_backend, phase, state,
                    started_at, finished_at, table_counts_json, catalog_digest,
                    object_count, object_bytes, error
                ) VALUES (
                    %s, 'sqlite', 'postgres', 'one-time', 'verified',
                    CURRENT_TIMESTAMP::text, CURRENT_TIMESTAMP::text, %s, %s, 0, 0, NULL
                )
                """,
                (migration_id, _json(table_counts), catalog_digest),
            )

        return {
            "status": "verified",
            "migration_version": MIGRATION_VERSION,
            "table_counts": table_counts,
            "catalog_digest": catalog_digest,
            "text_nul_bytes_normalized": normalized_nul_bytes,
            "source_files_ready_for_explicit_deletion": _source_file_candidates(sqlite_path),
        }
    finally:
        source.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="一次性把冻结的 QSou SQLite 目录只读导入 PostgreSQL"
    )
    parser.add_argument("--sqlite-path", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            migrate(args.sqlite_path, args.data_root),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
