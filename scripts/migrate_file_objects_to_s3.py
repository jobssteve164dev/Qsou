#!/usr/bin/env python3
"""One-time, hash-verified copy of legacy file objects into S3-compatible storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qsou_data.catalog import Catalog
from qsou_data.migration_state import OBJECT_IMPORT_VERSION
from qsou_data.objects import S3ObjectStore, configured_object_store


MIGRATION_VERSION = OBJECT_IMPORT_VERSION
BATCH_SIZE = 100


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_path(root: Path, key: str) -> Path:
    path = (root / key).resolve()
    if root != path and root not in path.parents:
        raise RuntimeError(f"对象键越界: {key}")
    return path


def _verified_target_payload(target: S3ObjectStore, key: str, checksum: str) -> bytes:
    payload = target.get_primary_bytes(key)
    if hashlib.sha256(payload).hexdigest() != checksum:
        raise RuntimeError(f"主对象哈希不一致: {key}")
    if not target.backup_bucket:
        raise RuntimeError("对象迁移要求配置独立备份桶")
    backup = target.get_backup_bytes(key)
    if hashlib.sha256(backup).hexdigest() != checksum:
        raise RuntimeError(f"备份对象哈希不一致: {key}")
    return payload


def _copy_object(
    row: Mapping[str, Any],
    *,
    source_root: Path,
    target: S3ObjectStore,
) -> tuple[int, int]:
    key = str(row["body_path"])
    checksum = str(row["content_hash"])
    source_path = _source_path(source_root, key)
    if source_path.is_file():
        payload = source_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != checksum:
            raise RuntimeError(f"本地源对象哈希不一致: {key}")
        target.put_once(key, payload, str(row.get("content_type") or "application/octet-stream"))
    else:
        payload = _verified_target_payload(target, key, checksum)
    _verified_target_payload(target, key, checksum)

    metadata_count = 0
    metadata_path = source_path.with_suffix(".json")
    if metadata_path.is_file():
        metadata_payload = metadata_path.read_bytes()
        metadata_key = str(Path(key).with_suffix(".json"))
        target.put_once(
            metadata_key,
            metadata_payload,
            "application/json",
        )
        _verified_target_payload(
            target,
            metadata_key,
            hashlib.sha256(metadata_payload).hexdigest(),
        )
        metadata_count = 1
    return len(payload), metadata_count


def _already_applied(catalog: Catalog) -> bool:
    with catalog.connection() as connection:
        return bool(
            connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s",
                (MIGRATION_VERSION,),
            ).fetchone()
        )


def migrate(data_root: Path) -> dict[str, Any]:
    data_root = data_root.resolve()
    catalog = Catalog(data_root)
    target = configured_object_store(data_root)
    if not isinstance(target, S3ObjectStore):
        raise RuntimeError("对象迁移要求 QSOU_OBJECT_STORAGE_BACKEND=s3")
    if not target.backup_bucket:
        raise RuntimeError("对象迁移要求配置独立备份桶")
    if _already_applied(catalog):
        return {"status": "already_verified", "migration_version": MIGRATION_VERSION}

    with catalog.connection() as connection:
        rows = connection.execute(
            """
            SELECT raw_object_id, body_path, content_hash, content_type
            FROM raw_objects ORDER BY raw_object_id
            """
        ).fetchall()

    manifest = hashlib.sha256()
    object_count = 0
    object_bytes = 0
    metadata_count = 0
    for row in rows:
        encoded = _json(
            [row["raw_object_id"], row["body_path"], row["content_hash"]]
        ).encode("utf-8")
        manifest.update(len(encoded).to_bytes(8, "big"))
        manifest.update(encoded)
        size, copied_metadata = _copy_object(
            row,
            source_root=data_root,
            target=target,
        )
        object_count += 1
        object_bytes += size
        metadata_count += copied_metadata

    details = {
        "object_count": object_count,
        "object_bytes": object_bytes,
        "metadata_count": metadata_count,
        "manifest_digest": manifest.hexdigest(),
        "primary_bucket": target.bucket,
        "backup_bucket": target.backup_bucket,
    }
    migration_id = uuid.uuid4().hex
    with catalog.connection() as connection:
        current_count = int(
            connection.execute("SELECT COUNT(*) AS count FROM raw_objects").fetchone()["count"]
        )
        if current_count != object_count:
            raise RuntimeError(
                f"对象迁移期间目录发生变化: before={object_count}, after={current_count}"
            )
        connection.execute(
            """
            INSERT INTO schema_migrations (version, applied_at, details_json)
            VALUES (%s, CURRENT_TIMESTAMP::text, %s)
            ON CONFLICT (version) DO UPDATE SET
                applied_at = excluded.applied_at,
                details_json = excluded.details_json
            """,
            (MIGRATION_VERSION, _json(details)),
        )
        connection.execute(
            """
            INSERT INTO migration_audits (
                migration_id, source_backend, target_backend, phase, state,
                started_at, finished_at, table_counts_json, catalog_digest,
                object_count, object_bytes, error
            ) VALUES (
                %s, 'file', 's3', 'one-time', 'verified',
                CURRENT_TIMESTAMP::text, CURRENT_TIMESTAMP::text, %s, %s, %s, %s, NULL
            )
            """,
            (
                migration_id,
                _json({"raw_objects": {"source": object_count, "target": object_count}}),
                details["manifest_digest"],
                object_count,
                object_bytes,
            ),
        )
    return {"status": "verified", "migration_version": MIGRATION_VERSION, **details}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="一次性把 QSou 本地不可变证据对象校验复制到主对象桶和备份桶"
    )
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.data_root), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
