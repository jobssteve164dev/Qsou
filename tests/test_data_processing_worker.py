import unittest
from contextlib import contextmanager
import json

from qsou_data.indexer import run_cycle
from qsou_data.processing import BaselineDocumentProcessor, run_processing_batch
from qsou_data.search_index import ElasticsearchIndex, IndexBatchError
from qsou_data.store import DataAssetStore


class BaselineDocumentProcessorTest(unittest.TestCase):
    def test_processing_preserves_source_document_and_builds_search_features(self):
        document = {
            "content_version_id": "version-1",
            "canonical_document_id": "document-1",
            "raw_object_id": "raw-1",
            "source_id": "official-source",
            "source": "官方来源",
            "url": "https://example.gov/reports/1",
            "title": "示例股份有限公司发布2026年度报告",
            "content": "<p>证券代码 600001。营业收入增长20%，净利润达到3亿元。</p>",
        }
        original = dict(document)

        result = BaselineDocumentProcessor().process(document)

        self.assertEqual(document, original)
        self.assertEqual(result["processing_version"], "qsou-baseline/1")
        self.assertEqual(
            result["processed_content"],
            "证券代码 600001。营业收入增长20%，净利润达到3亿元。",
        )
        self.assertIn("营业收入", result["keywords"])
        self.assertIn("财务指标", result["categories"])
        self.assertIn(
            {"text": "600001", "type": "stock_code"},
            result["entities"],
        )
        self.assertGreaterEqual(result["quality"]["score"], 0.6)
        self.assertTrue(result["quality"]["accepted"])


class ProcessingBatchTest(unittest.TestCase):
    def test_batch_persists_processing_before_projection_indexes_it(self):
        document = {
            "content_version_id": "version-1",
            "canonical_document_id": "document-1",
            "raw_object_id": "raw-1",
            "source_id": "official-source",
            "source": "官方来源",
            "url": "https://example.gov/policy/1",
            "title": "监管政策正式发布",
            "content": "监管机构正式发布政策，要求市场参与者完成信息披露。",
            "active": True,
        }

        class Store:
            def __init__(self):
                self.document = dict(document)
                self.saved = []
                self.marked = []

            def claim_processing_documents(self, _limit):
                return [dict(self.document)]

            def save_processing_result(self, content_version_id, processing):
                self.saved.append(content_version_id)
                self.document["processing"] = dict(processing)
                self.document["processed_at"] = processing["processed_at"]

            def mark_failed(self, ids, error):
                raise AssertionError((ids, error))

            def documents_for_index(self):
                return iter([])

            def pending_documents_for_index(self, _limit):
                return [dict(self.document)] if not self.marked else []

            def active_document_count(self):
                return 1

            def mark_indexed(self, ids):
                self.marked.extend(ids)

        class Index:
            def __init__(self):
                self.actions = []

            def ensure_ready(self):
                return None

            def index_documents(self, documents, *, projection_generation=None):
                self.assert_projection_generation(projection_generation)
                action_builder = ElasticsearchIndex.__new__(ElasticsearchIndex)
                action_builder.alias = "qsou_documents"
                for item in documents:
                    self.actions.append(action_builder._action(item))
                return [action["_id"] for action in self.actions]

            @staticmethod
            def assert_projection_generation(value):
                if value is not None:
                    raise AssertionError(value)

            def refresh(self):
                return None

            def active_document_count(self):
                return len(self.actions)

        store = Store()
        index = Index()
        _, result = run_cycle(
            store,
            index,
            processor=BaselineDocumentProcessor(),
            last_reconcile=100,
            reconcile_seconds=3600,
            batch_size=10,
            now=101,
        )

        self.assertEqual(store.saved, ["version-1"])
        self.assertEqual(store.marked, ["version-1"])
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["processing_failed"], 0)
        self.assertEqual(
            index.actions[0]["_source"]["content"],
            "监管机构正式发布政策，要求市场参与者完成信息披露。",
        )
        self.assertEqual(
            index.actions[0]["_source"]["processing_version"],
            "qsou-baseline/1",
        )

    def test_batch_records_processing_failure_without_indexing_unprocessed_document(self):
        class Store:
            failed = []

            @staticmethod
            def claim_processing_documents(_limit):
                return [{"content_version_id": "broken"}]

            @classmethod
            def mark_failed(cls, ids, error):
                cls.failed.append((list(ids), error))

        class Processor:
            @staticmethod
            def process(_document):
                raise ValueError("正文无法处理")

        result = run_processing_batch(Store(), Processor(), batch_size=5)

        self.assertEqual(
            result,
            {"claimed": 1, "processed": 0, "filtered": 0, "processing_failed": 1},
        )
        self.assertEqual(Store.failed, [(["broken"], "processing: 正文无法处理")])

    def test_batch_persists_rejected_quality_result_as_filtered(self):
        class Store:
            saved = []

            @staticmethod
            def claim_processing_documents(_limit):
                return [{"content_version_id": "low-quality"}]

            @classmethod
            def save_processing_result(cls, content_version_id, processing, *, state="processed"):
                cls.saved.append((content_version_id, processing, state))

        class Processor:
            @staticmethod
            def process(_document):
                return {
                    "processed_at": "2026-09-26T02:00:00Z",
                    "quality": {"score": 0.2, "accepted": False},
                }

        result = run_processing_batch(Store(), Processor(), batch_size=5)

        self.assertEqual(result["filtered"], 1)
        self.assertEqual(result["processed"], 0)
        self.assertEqual(Store.saved[0][2], "filtered")

    def test_transient_index_failure_keeps_processed_document_ready_for_retry(self):
        class Store:
            index_failures = []

            @staticmethod
            def documents_for_index():
                return iter([])

            @staticmethod
            def pending_documents_for_index(_limit):
                return [{"content_version_id": "version-1", "active": True}]

            @staticmethod
            def active_document_count():
                return 1

            @classmethod
            def record_index_failure(cls, ids, error):
                cls.index_failures.append((list(ids), error))

        class Index:
            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(_documents, *, projection_generation=None):
                raise RuntimeError("search unavailable")

        with self.assertRaisesRegex(RuntimeError, "search unavailable"):
            run_cycle(
                Store(),
                Index(),
                last_reconcile=100,
                reconcile_seconds=3600,
                batch_size=10,
                now=101,
            )
        with self.assertRaisesRegex(RuntimeError, "search unavailable"):
            run_cycle(
                Store(),
                Index(),
                last_reconcile=100,
                reconcile_seconds=3600,
                batch_size=10,
                now=102,
            )

        self.assertEqual(
            Store.index_failures,
            [
                (["version-1"], "indexing: search unavailable"),
                (["version-1"], "indexing: search unavailable"),
            ],
        )

    def test_partial_bulk_failure_marks_successes_and_isolates_only_rejected_ids(self):
        class Store:
            indexed = []
            failures = []

            @staticmethod
            def pending_documents_for_index(_limit):
                return [
                    {"content_version_id": "ok", "active": True},
                    {"content_version_id": "poison", "active": True},
                ]

            @staticmethod
            def active_document_count():
                return 2

            @classmethod
            def mark_indexed(cls, ids):
                cls.indexed.extend(ids)

            @classmethod
            def mark_failed(cls, ids, error):
                cls.failures.append((list(ids), error))

        class Index:
            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(_documents, *, projection_generation=None):
                raise IndexBatchError(
                    "one rejected",
                    indexed_ids=["ok"],
                    failed_ids=["poison"],
                )

            @staticmethod
            def refresh():
                return None

        with self.assertRaisesRegex(IndexBatchError, "one rejected"):
            run_cycle(
                Store(),
                Index(),
                last_reconcile=100,
                reconcile_seconds=3600,
                batch_size=10,
                now=101,
            )

        self.assertEqual(Store.indexed, ["ok"])
        self.assertEqual(Store.failures, [(["poison"], "indexing: one rejected")])

    def test_bulk_backpressure_keeps_document_processed_for_next_cycle(self):
        class Store:
            failures = []
            retries = []

            @staticmethod
            def pending_documents_for_index(_limit):
                return [{"content_version_id": "busy", "active": True}]

            @staticmethod
            def active_document_count():
                return 1

            @classmethod
            def mark_failed(cls, ids, error):
                cls.failures.append((list(ids), error))

            @classmethod
            def record_index_failure(cls, ids, error):
                cls.retries.append((list(ids), error))

        class Index:
            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(_documents, *, projection_generation=None):
                raise IndexBatchError(
                    "backpressure",
                    indexed_ids=[],
                    failed_ids=[],
                    retryable_ids=["busy"],
                )

        with self.assertRaisesRegex(IndexBatchError, "backpressure"):
            run_cycle(
                Store(),
                Index(),
                last_reconcile=100,
                reconcile_seconds=3600,
                batch_size=10,
                now=101,
            )

        self.assertEqual(Store.failures, [])
        self.assertEqual(Store.retries, [(["busy"], "indexing: backpressure")])

    def test_reconcile_partial_failure_never_deletes_from_incomplete_generation(self):
        class Store:
            indexed = []
            failures = []

            @staticmethod
            def documents_for_index():
                return iter(
                    [
                        {"content_version_id": "ok", "active": True},
                        {"content_version_id": "poison", "active": True},
                    ]
                )

            @classmethod
            def mark_indexed(cls, ids):
                cls.indexed.extend(ids)

            @classmethod
            def mark_failed(cls, ids, error):
                cls.failures.append((list(ids), error))

        class Index:
            deleted = False

            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(_documents, *, projection_generation=None):
                self.assertIsNotNone(projection_generation)
                raise IndexBatchError(
                    "one rejected",
                    indexed_ids=["ok"],
                    failed_ids=["poison"],
                )

            @staticmethod
            def refresh():
                return None

            @classmethod
            def delete_stale(cls, _generation):
                cls.deleted = True
                return 0

        with self.assertRaisesRegex(IndexBatchError, "one rejected"):
            run_cycle(
                Store(),
                Index(),
                last_reconcile=0,
                reconcile_seconds=3600,
                batch_size=10,
                now=3601,
            )

        self.assertEqual(Store.indexed, ["ok"])
        self.assertEqual(Store.failures, [(["poison"], "indexing: one rejected")])
        self.assertFalse(Index.deleted)

    def test_filtered_document_does_not_create_projection_count_mismatch(self):
        class Store:
            @staticmethod
            def claim_processing_documents(_limit):
                return [{"content_version_id": "filtered"}]

            @staticmethod
            def save_processing_result(_content_version_id, _processing, *, state="processed"):
                self.assertEqual(state, "filtered")

            @staticmethod
            def pending_documents_for_index(_limit):
                return []

            @staticmethod
            def projectable_active_document_count():
                return 0

        class Processor:
            @staticmethod
            def process(_document):
                return {"quality": {"accepted": False}}

        class Index:
            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def active_document_count():
                return 0

        _, result = run_cycle(
            Store(),
            Index(),
            processor=Processor(),
            last_reconcile=100,
            reconcile_seconds=3600,
            batch_size=10,
            now=101,
        )

        self.assertTrue(result["converged"])
        self.assertEqual(result["active_documents"], 0)
        self.assertEqual(result["filtered"], 1)


class ProcessingStoreContractTest(unittest.TestCase):
    def test_claim_atomically_recovers_pending_and_stale_processing_documents(self):
        calls = []

        class Result:
            def __init__(self, rows):
                self.rows = rows

            def fetchall(self):
                return self.rows

            def fetchone(self):
                return self.rows[0] if self.rows else None

        class Connection:
            @staticmethod
            def execute(sql, parameters=()):
                calls.append((sql, parameters))
                if "RETURNING o.content_version_id" in sql:
                    return Result(
                        [
                            {"content_version_id": "pending-version"},
                            {"content_version_id": "stale-version"},
                        ]
                    )
                if "SELECT document_json FROM standard_documents" in sql:
                    version = parameters[0]
                    return Result(
                        [
                            {
                                "document_json": json.dumps(
                                    {"content_version_id": version, "title": version}
                                )
                            }
                        ]
                    )
                raise AssertionError(sql)

        @contextmanager
        def connection():
            yield Connection()

        store = DataAssetStore.__new__(DataAssetStore)
        store._connection = connection

        documents = store.claim_processing_documents(2, stale_after_seconds=300)

        self.assertEqual(
            [document["content_version_id"] for document in documents],
            ["pending-version", "stale-version"],
        )
        claim_sql, claim_parameters = calls[0]
        self.assertIn("FOR UPDATE OF o SKIP LOCKED", claim_sql)
        self.assertIn("o.state = 'pending'", claim_sql)
        self.assertIn("o.state = 'processing'", claim_sql)
        self.assertIn("attempts = o.attempts + 1", claim_sql)
        self.assertIn(2, claim_parameters)

    def test_save_processing_result_keeps_source_content_and_marks_processed(self):
        calls = []
        original = {
            "content_version_id": "version-1",
            "title": "原始标题",
            "content": "原始标准正文",
            "content_hash": "source-hash",
        }

        class Result:
            @staticmethod
            def fetchone():
                return {"document_json": json.dumps(original), "active": True}

        class Connection:
            @staticmethod
            def execute(sql, parameters=()):
                calls.append((sql, parameters))
                return Result()

        @contextmanager
        def connection():
            yield Connection()

        store = DataAssetStore.__new__(DataAssetStore)
        store._connection = connection
        processing = {
            "processing_version": "qsou-baseline/1",
            "processed_at": "2026-09-26T02:00:00Z",
            "processed_content": "清洗后的正文",
            "quality": {"score": 1.0, "accepted": True},
        }

        store.save_processing_result("version-1", processing)

        update_document = next(call for call in calls if "UPDATE standard_documents" in call[0])
        stored = json.loads(update_document[1][1])
        self.assertEqual(stored["content"], "原始标准正文")
        self.assertEqual(stored["content_hash"], "source-hash")
        self.assertEqual(stored["processing"], processing)
        update_outbox = next(call for call in calls if "UPDATE processing_outbox" in call[0])
        self.assertEqual(update_outbox[1][0], "processed")

    def test_index_queue_excludes_active_documents_until_processing_finishes(self):
        calls = []

        class Result:
            @staticmethod
            def fetchall():
                return []

        class Connection:
            @staticmethod
            def execute(sql, parameters=()):
                calls.append((sql, parameters))
                return Result()

        @contextmanager
        def connection():
            yield Connection()

        store = DataAssetStore.__new__(DataAssetStore)
        store._connection = connection

        self.assertEqual(store.pending_documents_for_index(25), [])

        query = calls[0][0]
        self.assertIn("JOIN processing_outbox o USING(content_version_id)", query)
        self.assertIn("o.state IN ('processed', 'indexed')", query)
        self.assertNotIn("d.active = 0", query)


if __name__ == "__main__":
    unittest.main()
