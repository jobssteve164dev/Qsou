"""Legacy SQLite catalog migration and rollback verification.

This module only moves data when explicitly invoked. Selecting PostgreSQL as the
runtime catalog does not silently import or delete the legacy SQLite catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from .catalog import normalize_catalog_value
from .store import DataAssetError, DataAssetStore, _json, default_data_root, utc_now


MIGRATION_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("raw_objects", ("raw_object_id",)),
    ("standard_documents", ("content_version_id",)),
    ("document_evidence", ("content_version_id", "raw_object_id")),
    ("processing_outbox", ("content_version_id",)),
    ("adapter_runs", ("run_id",)),
    ("source_cursors", ("source_id",)),
    ("adapter_run_requests", ("request_id",)),
)
MIGRATION_VERSION = "legacy-sqlite-to-postgres-object-storage-v2"
BATCH_SIZE = 100


def _row_digest(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> str:
    digest = hashlib.sha256()
    _update_digest(digest, rows, columns)
    return digest.hexdigest()


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


def _table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")]


def _upsert_sql(table: str, columns: Sequence[str], keys: Sequence[str]) -> str:
    quoted_columns = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    conflict = ", ".join(keys)
    updates = [column for column in columns if column not in keys]
    if updates:
        action = "DO UPDATE SET " + ", ".join(
            f"{column} = excluded.{column}" for column in updates
        )
    else:
        action = "DO NOTHING"
    return (
        f"INSERT INTO {table} ({quoted_columns}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict}) {action}"
    )


class LegacySqliteMigrator:
    """Idempotently copy the legacy catalog and immutable evidence objects."""

    def __init__(
        self,
        target: DataAssetStore | None,
        *,
        legacy_catalog: Path | None = None,
        legacy_root: Path | None = None,
    ) -> None:
        self.target = target
        self.legacy_root = Path(
            legacy_root or (target.root if target else default_data_root())
        ).resolve()
        self.legacy_catalog = Path(
            legacy_catalog or self.legacy_root / "catalog.sqlite3"
        ).resolve()

    def run(self, phase: str = "backfill") -> Dict[str, Any]:
        if phase not in {"backfill", "final"}:
            raise ValueError(f"不支持的迁移阶段: {phase}")
        if not self.legacy_catalog.is_file():
            raise DataAssetError(f"旧 SQLite 目录库不存在: {self.legacy_catalog}")
        if self.target is None:
            raise DataAssetError("执行迁移时缺少目标目录库")
        if (
            self.target.catalog.backend == "sqlite"
            and self.target.catalog.sqlite_path.resolve() == self.legacy_catalog
        ):
            raise DataAssetError("迁移源与目标不能是同一个 SQLite 目录库")
        if phase == "final" and os.getenv("QSOU_SQLITE_WRITES_FROZEN", "").lower() != "true":
            raise DataAssetError("最终增量迁移前必须确认 QSOU_SQLITE_WRITES_FROZEN=true")

        migration_id = uuid.uuid4().hex
        started_at = utc_now()
        try:
            source = sqlite3.connect(f"file:{self.legacy_catalog}?mode=ro", uri=True, timeout=30)
            source.row_factory = sqlite3.Row
            source.execute("PRAGMA foreign_keys = ON")
            source_version = int(source.execute("PRAGMA data_version").fetchone()[0])
            try:
                report = self._copy_and_verify(
                    source,
                    phase,
                    migration_id,
                    started_at,
                    source_version,
                )
            finally:
                source.close()
            return report
        except Exception as exc:
            self._record_failure(migration_id, phase, started_at, exc)
            raise

    def rollback_check(self) -> Dict[str, Any]:
        """Prove the untouched SQLite/file path can still serve as rollback source."""
        if not self.legacy_catalog.is_file():
            raise DataAssetError(f"旧 SQLite 目录库不存在: {self.legacy_catalog}")
        connection = sqlite3.connect(f"file:{self.legacy_catalog}?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise DataAssetError(f"旧 SQLite 完整性检查失败: {integrity}")
            cursor = connection.execute(
                "SELECT raw_object_id, body_path, content_hash FROM raw_objects ORDER BY raw_object_id"
            )
            object_count = 0
            total_bytes = 0
            while True:
                rows = cursor.fetchmany(BATCH_SIZE)
                if not rows:
                    break
                for row in rows:
                    payload = self._legacy_object(row["body_path"])
                    if hashlib.sha256(payload).hexdigest() != row["content_hash"]:
                        raise DataAssetError(f"旧证据对象哈希不一致: {row['raw_object_id']}")
                    object_count += 1
                    total_bytes += len(payload)
            return {
                "status": "rollback_ready",
                "catalog": str(self.legacy_catalog),
                "raw_objects": object_count,
                "object_bytes": total_bytes,
            }
        finally:
            connection.close()

    def _copy_and_verify(
        self,
        source: sqlite3.Connection,
        phase: str,
        migration_id: str,
        started_at: str,
        source_version: int,
    ) -> Dict[str, Any]:
        if self.target is None:
            raise DataAssetError("执行迁移时缺少目标目录库")
        table_counts: Dict[str, Dict[str, int]] = {}
        table_digests: Dict[str, str] = {}
        text_nul_bytes_normalized = 0
        object_count, object_bytes = self._copy_objects(source)

        with self.target._connection() as target:
            target.execute("BEGIN IMMEDIATE")
            for table, keys in MIGRATION_TABLES:
                columns = _table_columns(source, table)
                if not columns:
                    raise DataAssetError(f"旧目录库缺少迁移表: {table}")
                source_cursor = source.execute(
                    f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(keys)}"
                )
                source_count = 0
                source_hasher = hashlib.sha256()
                while True:
                    source_rows = source_cursor.fetchmany(BATCH_SIZE)
                    if not source_rows:
                        break
                    normalized_rows = []
                    for row in source_rows:
                        values = []
                        for column in columns:
                            value = row[column]
                            if isinstance(value, str):
                                text_nul_bytes_normalized += value.count("\x00")
                            values.append(normalize_catalog_value(value))
                        normalized_rows.append(tuple(values))
                    target.executemany(
                        _upsert_sql(table, columns, keys),
                        normalized_rows,
                    )
                    source_count += _update_digest(source_hasher, source_rows, columns)
                source_digest = source_hasher.hexdigest()
                target_cursor = target.execute(
                    f"SELECT {', '.join(columns)} FROM {table} ORDER BY {', '.join(keys)}"
                )
                target_count, target_digest = _cursor_digest(target_cursor, columns)
                if source_count != target_count or source_digest != target_digest:
                    raise DataAssetError(
                        f"目录表迁移校验失败: {table}: "
                        f"source={source_count}/{source_digest}, "
                        f"target={target_count}/{target_digest}"
                    )
                table_counts[table] = {
                    "source": source_count,
                    "target": target_count,
                }
                table_digests[table] = source_digest

            if phase == "final":
                ending_version = int(source.execute("PRAGMA data_version").fetchone()[0])
                if ending_version != source_version:
                    raise DataAssetError("最终增量迁移期间旧 SQLite 仍发生写入")

            catalog_digest = hashlib.sha256(_json(table_digests).encode("utf-8")).hexdigest()
            finished_at = utc_now()
            details = {
                "phase": phase,
                "table_counts": table_counts,
                "catalog_digest": catalog_digest,
                "object_count": object_count,
                "object_bytes": object_bytes,
                "text_nul_bytes_normalized": text_nul_bytes_normalized,
            }
            version = f"{MIGRATION_VERSION}-{phase}"
            target.execute(
                """
                INSERT INTO schema_migrations (version, applied_at, details_json)
                VALUES (?, ?, ?)
                ON CONFLICT(version) DO UPDATE SET
                    applied_at = excluded.applied_at,
                    details_json = excluded.details_json
                """,
                (version, finished_at, _json(details)),
            )
            target.execute(
                """
                INSERT INTO migration_audits (
                    migration_id, source_backend, target_backend, phase, state,
                    started_at, finished_at, table_counts_json, catalog_digest,
                    object_count, object_bytes, error
                ) VALUES (?, 'sqlite', ?, ?, 'verified', ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    migration_id,
                    self.target.catalog.backend,
                    phase,
                    started_at,
                    finished_at,
                    _json(table_counts),
                    catalog_digest,
                    object_count,
                    object_bytes,
                ),
            )

        return {
            "status": "verified",
            "migration_id": migration_id,
            "phase": phase,
            **details,
        }

    def _copy_objects(self, source: sqlite3.Connection) -> tuple[int, int]:
        if self.target is None:
            raise DataAssetError("执行迁移时缺少目标对象存储")
        cursor = source.execute(
            """
            SELECT raw_object_id, body_path, content_hash, content_type
            FROM raw_objects ORDER BY raw_object_id
            """
        )
        object_count = 0
        total_bytes = 0
        while True:
            rows = cursor.fetchmany(BATCH_SIZE)
            if not rows:
                break
            for row in rows:
                key = str(row["body_path"])
                payload = self._legacy_object(key)
                checksum = hashlib.sha256(payload).hexdigest()
                if checksum != row["content_hash"]:
                    raise DataAssetError(f"旧证据对象哈希不一致: {row['raw_object_id']}")
                self.target.object_store.put_once(key, payload, row["content_type"])
                stored = self.target.object_store.get_primary_bytes(key)
                if hashlib.sha256(stored).hexdigest() != checksum:
                    raise DataAssetError(f"目标证据对象哈希不一致: {row['raw_object_id']}")
                if getattr(self.target.object_store, "backup_bucket", None):
                    backup = self.target.object_store.get_backup_bytes(key)
                    if hashlib.sha256(backup).hexdigest() != checksum:
                        raise DataAssetError(f"备份证据对象哈希不一致: {row['raw_object_id']}")

                metadata_path = (self.legacy_root / key).with_suffix(".json")
                if metadata_path.is_file():
                    self.target.object_store.put_once(
                        str(Path(key).with_suffix(".json")),
                        metadata_path.read_bytes(),
                        "application/json",
                        verify_existing=False,
                    )
                object_count += 1
                total_bytes += len(payload)
        return object_count, total_bytes

    def _legacy_object(self, key: str) -> bytes:
        path = (self.legacy_root / key).resolve()
        if self.legacy_root != path and self.legacy_root not in path.parents:
            raise DataAssetError(f"旧证据对象路径越界: {key}")
        if not path.is_file():
            raise DataAssetError(f"旧证据对象不存在: {key}")
        return path.read_bytes()

    def _record_failure(
        self,
        migration_id: str,
        phase: str,
        started_at: str,
        error: Exception,
    ) -> None:
        if self.target is None:
            return
        try:
            with self.target._connection() as target:
                target.execute(
                    """
                    INSERT INTO migration_audits (
                        migration_id, source_backend, target_backend, phase, state,
                        started_at, finished_at, object_count, object_bytes, error
                    ) VALUES (?, 'sqlite', ?, ?, 'failed', ?, ?, 0, 0, ?)
                    ON CONFLICT(migration_id) DO UPDATE SET
                        state = 'failed', finished_at = excluded.finished_at,
                        error = excluded.error
                    """,
                    (
                        migration_id,
                        self.target.catalog.backend,
                        phase,
                        started_at,
                        utc_now(),
                        str(error)[:4000],
                    ),
                )
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="QSou SQLite 目录库迁移与回滚验证")
    parser.add_argument("phase", choices=("backfill", "final", "rollback-check"))
    parser.add_argument("--legacy-root", type=Path)
    parser.add_argument("--legacy-catalog", type=Path)
    args = parser.parse_args()

    if args.phase == "rollback-check":
        migrator = LegacySqliteMigrator(
            None,
            legacy_root=args.legacy_root,
            legacy_catalog=args.legacy_catalog,
        )
        result = migrator.rollback_check()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    store = DataAssetStore()
    if store.catalog.backend != "postgres":
        parser.error("实际迁移必须设置 QSOU_CATALOG_BACKEND=postgres")
    migrator = LegacySqliteMigrator(
        store,
        legacy_root=args.legacy_root,
        legacy_catalog=args.legacy_catalog,
    )
    result = migrator.run(args.phase)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
