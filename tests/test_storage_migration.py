import io
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qsou_data.catalog import PostgresConnection, TEXT_NUL_REPLACEMENT
from qsou_data.objects import ObjectStorageError, S3ObjectStore
from scripts.migrate_file_objects_to_s3 import _copy_object, _source_path


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
        self.environment = patch.dict(os.environ, {"QSOU_OBJECT_STORAGE_BACKEND": "file"})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_postgres_connection_normalizes_nul_without_sql_translation(self) -> None:
        class FakeResult:
            returns_rows = False
            rowcount = 1

        class FakeConnection:
            def __init__(self) -> None:
                self.calls = []

            def exec_driver_sql(self, sql, parameters=None):
                self.calls.append((sql, parameters))
                return FakeResult()

        fake = FakeConnection()
        postgres = PostgresConnection(fake)
        postgres.execute("INSERT INTO sample (value) VALUES (%s)", ("one\x00value",))
        postgres.executemany(
            "INSERT INTO sample (value) VALUES (%s)",
            [("two\x00value",)],
        )
        self.assertEqual(
            fake.calls,
            [
                (
                    "INSERT INTO sample (value) VALUES (%s)",
                    (f"one{TEXT_NUL_REPLACEMENT}value",),
                ),
                (
                    "INSERT INTO sample (value) VALUES (%s)",
                    [(f"two{TEXT_NUL_REPLACEMENT}value",)],
                ),
            ],
        )

    def test_file_object_migration_requires_safe_paths_and_verifies_both_buckets(self) -> None:
        client = _MemoryS3Client()
        target = S3ObjectStore.__new__(S3ObjectStore)
        target.endpoint_url = "https://objects.example"
        target.bucket = "primary"
        target.backup_bucket = "backup"
        target.client = client
        key = "objects/aa/evidence.body"
        payload = b"immutable evidence"
        source = self.root / key
        source.parent.mkdir(parents=True)
        source.write_bytes(payload)
        source.with_suffix(".json").write_text('{"source":"test"}', encoding="utf-8")

        object_bytes, metadata_count = _copy_object(
            {
                "body_path": key,
                "content_hash": hashlib.sha256(payload).hexdigest(),
                "content_type": "application/octet-stream",
            },
            source_root=self.root.resolve(),
            target=target,
        )
        self.assertEqual(object_bytes, len(payload))
        self.assertEqual(metadata_count, 1)
        self.assertEqual(target.get_primary_bytes(key), payload)
        self.assertEqual(target.get_backup_bytes(key), payload)
        with self.assertRaisesRegex(RuntimeError, "对象键越界"):
            _source_path(self.root.resolve(), "../outside")

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
