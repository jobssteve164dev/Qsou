import io
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qsou_data import DataAssetError, DataAssetStore, SourceRegistry
from qsou_data.catalog import (
    PostgresConnection,
    TEXT_NUL_REPLACEMENT,
    _postgres_sql,
)
from qsou_data.migrate import LegacySqliteMigrator
from qsou_data.objects import ObjectStorageError, S3ObjectStore
from qsou_data.start_api import run_configured_migration
from qsou_data.verify import verify_storage


class _MissingObject(Exception):
    response = {"Error": {"Code": "404"}}


class _MemoryS3Client:
    def __init__(self) -> None:
        self.objects = {}
        self.head_error = None

    def head_object(self, *, Bucket, Key):
        if self.head_error:
            raise self.head_error
        try:
            value = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise _MissingObject() from exc
        return {"Metadata": value["Metadata"], "ContentType": value["ContentType"]}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[(Bucket, Key)] = {
            "Body": bytes(Body),
            "ContentType": ContentType,
            "Metadata": dict(Metadata),
        }

    def get_object(self, *, Bucket, Key):
        try:
            value = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise _MissingObject() from exc
        return {
            "Body": io.BytesIO(value["Body"]),
            "ContentType": value["ContentType"],
            "Metadata": value["Metadata"],
        }


class StorageMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.environment = patch.dict(
            os.environ,
            {
                "QSOU_CATALOG_BACKEND": "sqlite",
                "QSOU_OBJECT_STORAGE_BACKEND": "file",
            },
            clear=False,
        )
        self.environment.start()
        self.registry = SourceRegistry()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_sqlite_backfill_final_delta_and_rollback_check(self) -> None:
        source_root = self.root / "legacy"
        target_root = self.root / "target"
        source = DataAssetStore(root=source_root, registry=self.registry)
        evidence = source.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/102000001.html",
            status_code=200,
            response_headers={"Content-Type": "text/html"},
            body="第一财经迁移证据".encode("utf-8"),
            fetched_at="2026-08-09T00:00:00Z",
            content_type="text/html",
            encoding="utf-8",
        )
        source.register_document(
            {
                "source_id": "yicai",
                "source_document_id": "102000001",
                "raw_object_id": evidence["raw_object_id"],
                "title": "迁移验证",
                "content": "目录与对象必须一起通过校验。",
                "url": evidence["url"],
                "fetched_at": "2026-08-09T00:00:00Z",
            }
        )
        with sqlite3.connect(source.catalog_path) as legacy_connection:
            legacy_connection.execute(
                "UPDATE raw_objects SET collector = ? WHERE raw_object_id = ?",
                ("legacy\x00collector", evidence["raw_object_id"]),
            )

        target = DataAssetStore(root=target_root, registry=self.registry)
        migrator = LegacySqliteMigrator(
            target,
            legacy_root=source_root,
            legacy_catalog=source.catalog_path,
        )
        report = migrator.run("backfill")
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["text_nul_bytes_normalized"], 1)
        self.assertEqual(report["object_count"], 1)
        self.assertEqual(report["table_counts"]["raw_objects"], {"source": 1, "target": 1})
        self.assertEqual(
            target.evidence_body_path(evidence["raw_object_id"]).read_bytes(),
            "第一财经迁移证据".encode("utf-8"),
        )
        with target._connection() as connection:
            migrated = connection.execute(
                "SELECT collector FROM raw_objects WHERE raw_object_id = ?",
                (evidence["raw_object_id"],),
            ).fetchone()
        self.assertEqual(
            migrated["collector"],
            f"legacy{TEXT_NUL_REPLACEMENT}collector",
        )
        with patch.dict(os.environ, {"QSOU_SQLITE_WRITES_FROZEN": ""}):
            with self.assertRaisesRegex(DataAssetError, "QSOU_SQLITE_WRITES_FROZEN"):
                migrator.run("final")
        with self.assertRaisesRegex(DataAssetError, "备份桶"):
            verify_storage(target, require_backup=True)

        source.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/102000001.html",
            status_code=200,
            response_headers={"Content-Type": "text/html"},
            body="第一财经迁移证据".encode("utf-8"),
            fetched_at="2026-08-09T00:10:00Z",
            content_type="text/html",
            encoding="utf-8",
        )
        with patch.dict(os.environ, {"QSOU_SQLITE_WRITES_FROZEN": "true"}):
            final = migrator.run("final")
        self.assertEqual(final["phase"], "final")
        self.assertEqual(target.get_evidence(evidence["raw_object_id"])["fetch_count"], 2)

        rollback = migrator.rollback_check()
        self.assertEqual(rollback["status"], "rollback_ready")
        self.assertEqual(rollback["raw_objects"], 1)

        acceptance = verify_storage(target)
        self.assertEqual(acceptance["status"], "verified")
        self.assertEqual(acceptance["object_count"], 1)
        self.assertFalse(acceptance["backup_verified"])

    def test_postgres_translation_keeps_conflict_semantics(self) -> None:
        self.assertEqual(
            _postgres_sql("INSERT OR IGNORE INTO sample (id) VALUES (?)"),
            "INSERT INTO sample (id) VALUES (%s) ON CONFLICT DO NOTHING",
        )
        self.assertEqual(
            _postgres_sql(
                "INSERT INTO sample (id, value) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET value = excluded.value"
            ),
            "INSERT INTO sample (id, value) VALUES (%s, %s) "
            "ON CONFLICT(id) DO UPDATE SET value = excluded.value",
        )

    def test_catalog_connections_normalize_nul_for_future_writes(self) -> None:
        source_root = self.root / "normalized-source"
        source = DataAssetStore(root=source_root, registry=self.registry)
        evidence = source.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/102000002.html",
            status_code=200,
            response_headers={"Content-Type": "text/html"},
            body=b"normalized",
            fetched_at="2026-08-09T00:00:00Z",
        )
        document = source.register_document(
            {
                "source_id": "yicai",
                "source_document_id": "102000002",
                "raw_object_id": evidence["raw_object_id"],
                "title": "future\x00title",
                "content": "future\x00content",
                "url": evidence["url"],
                "fetched_at": "2026-08-09T00:00:00Z",
            }
        )
        self.assertEqual(document["title"], f"future{TEXT_NUL_REPLACEMENT}title")
        self.assertEqual(document["content"], f"future{TEXT_NUL_REPLACEMENT}content")

        class FakeCursor:
            def __init__(self) -> None:
                self.parameters = None

            def executemany(self, _sql, parameters) -> None:
                self.parameters = list(parameters)

        class FakeConnection:
            def __init__(self) -> None:
                self.parameters = None
                self.cursor_instance = FakeCursor()

            def execute(self, _sql, parameters):
                self.parameters = parameters
                return self

            def cursor(self):
                return self.cursor_instance

        fake = FakeConnection()
        postgres = PostgresConnection(fake)
        postgres.execute("INSERT INTO sample (value) VALUES (?)", ("one\x00value",))
        self.assertEqual(fake.parameters, (f"one{TEXT_NUL_REPLACEMENT}value",))
        postgres.executemany(
            "INSERT INTO sample (value) VALUES (?)",
            [("two\x00value",)],
        )
        self.assertEqual(
            fake.cursor_instance.parameters,
            [(f"two{TEXT_NUL_REPLACEMENT}value",)],
        )

    def test_backfill_uses_one_snapshot_while_collector_keeps_writing(self) -> None:
        source_root = self.root / "concurrent-source"
        target_root = self.root / "concurrent-target"
        source = DataAssetStore(root=source_root, registry=self.registry)
        first_evidence = source.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/102000003.html",
            status_code=200,
            response_headers={"Content-Type": "text/html"},
            body=b"first",
            fetched_at="2026-08-09T00:00:00Z",
        )
        source.register_document(
            {
                "source_id": "yicai",
                "source_document_id": "102000003",
                "raw_object_id": first_evidence["raw_object_id"],
                "title": "first",
                "content": "first",
                "url": first_evidence["url"],
                "fetched_at": "2026-08-09T00:00:00Z",
            }
        )
        target = DataAssetStore(root=target_root, registry=self.registry)

        class ConcurrentWriteMigrator(LegacySqliteMigrator):
            wrote_during_migration = False

            def _copy_objects(self, connection):
                result = super()._copy_objects(connection)
                if not self.wrote_during_migration:
                    self.wrote_during_migration = True
                    second_evidence = source.archive_response(
                        source_id="yicai",
                        url="https://www.yicai.com/news/102000004.html",
                        status_code=200,
                        response_headers={"Content-Type": "text/html"},
                        body=b"second",
                        fetched_at="2026-08-09T00:01:00Z",
                    )
                    source.register_document(
                        {
                            "source_id": "yicai",
                            "source_document_id": "102000004",
                            "raw_object_id": second_evidence["raw_object_id"],
                            "title": "second",
                            "content": "second",
                            "url": second_evidence["url"],
                            "fetched_at": "2026-08-09T00:01:00Z",
                        }
                    )
                return result

        migrator = ConcurrentWriteMigrator(
            target,
            legacy_root=source_root,
            legacy_catalog=source.catalog_path,
        )
        first_report = migrator.run("backfill")
        self.assertEqual(
            first_report["table_counts"]["raw_objects"],
            {"source": 1, "target": 1},
        )
        self.assertEqual(
            first_report["table_counts"]["document_evidence"],
            {"source": 1, "target": 1},
        )

        second_report = migrator.run("backfill")
        self.assertEqual(
            second_report["table_counts"]["raw_objects"],
            {"source": 2, "target": 2},
        )
        self.assertEqual(
            second_report["table_counts"]["document_evidence"],
            {"source": 2, "target": 2},
        )

    def test_startup_backfill_restores_sqlite_runtime_backend(self) -> None:
        report = {"status": "verified", "phase": "backfill"}
        with (
            patch.dict(
                os.environ,
                {
                    "QSOU_CATALOG_BACKEND": "sqlite",
                    "QSOU_MIGRATION_PHASE": "backfill",
                    "DATABASE_URL": "postgresql://redacted",
                },
            ),
            patch("qsou_data.start_api.DataAssetStore") as store_class,
            patch("qsou_data.start_api.LegacySqliteMigrator") as migrator_class,
        ):
            migrator_class.return_value.run.return_value = report
            self.assertEqual(run_configured_migration(), report)
            self.assertEqual(os.environ["QSOU_CATALOG_BACKEND"], "sqlite")
            store_class.assert_called_once_with()
            migrator_class.return_value.run.assert_called_once_with("backfill")

    def test_startup_backfill_failure_keeps_sqlite_runtime_available(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "QSOU_CATALOG_BACKEND": "sqlite",
                    "QSOU_MIGRATION_PHASE": "backfill",
                    "DATABASE_URL": "postgresql://redacted",
                },
            ),
            patch("qsou_data.start_api.DataAssetStore"),
            patch("qsou_data.start_api.LegacySqliteMigrator") as migrator_class,
        ):
            migrator_class.return_value.run.side_effect = RuntimeError("target rejected text")
            report = run_configured_migration()
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["phase"], "backfill")
            self.assertEqual(report["runtime_backend"], "sqlite")
            self.assertEqual(os.environ["QSOU_CATALOG_BACKEND"], "sqlite")

    def test_startup_final_requires_postgres_runtime(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QSOU_CATALOG_BACKEND": "sqlite",
                "QSOU_MIGRATION_PHASE": "final",
            },
        ):
            with self.assertRaisesRegex(DataAssetError, "QSOU_CATALOG_BACKEND=postgres"):
                run_configured_migration()

    def test_startup_verify_requires_postgres_runtime(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QSOU_CATALOG_BACKEND": "sqlite",
                "QSOU_MIGRATION_PHASE": "verify",
            },
        ):
            with self.assertRaisesRegex(DataAssetError, "生产验收要求"):
                run_configured_migration()

    def test_s3_primary_backup_cache_and_restore_are_hash_checked(self) -> None:
        client = _MemoryS3Client()
        store = S3ObjectStore.__new__(S3ObjectStore)
        store.endpoint_url = "https://objects.example"
        store.bucket = "primary"
        store.backup_bucket = "backup"
        store.client = client
        key = "objects/aa/evidence.body"
        payload = b"immutable evidence"

        store.put_once(key, payload, "application/octet-stream")
        self.assertEqual(store.get_bytes(key), payload)
        self.assertEqual(store.get_backup_bytes(key), payload)
        materialized = store.materialize(key, self.root / "cache")
        self.assertEqual(materialized.read_bytes(), payload)
        self.assertIn(hashlib.sha256(payload).hexdigest(), materialized.parts)
        materialized.write_bytes(b"corrupt cache")
        recovered = store.materialize(key, self.root / "cache")
        self.assertNotEqual(recovered, materialized)
        self.assertEqual(recovered.read_bytes(), payload)

        with self.assertRaises(ObjectStorageError):
            store.put_once(key, b"different", "application/octet-stream")

        client.objects.pop(("primary", key))
        self.assertEqual(store.get_bytes(key), payload)
        store.restore_from_backup(key)
        self.assertEqual(store.get_bytes(key), payload)

        client.head_error = RuntimeError("network unavailable")
        with self.assertRaises(ObjectStorageError):
            store.exists(key)


if __name__ == "__main__":
    unittest.main()
