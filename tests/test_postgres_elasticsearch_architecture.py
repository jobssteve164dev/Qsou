import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_mock_engine
import yaml

from qsou_data.catalog import CatalogConfigurationError, _postgres_url
from qsou_data.indexer import run_cycle
from qsou_data.indexer_state import read_indexer_state, write_indexer_state
from qsou_data.migration_state import (
    ALEMBIC_REVISION,
    OBJECT_IMPORT_VERSION,
    SQLITE_IMPORT_VERSION,
    migration_state,
    required_migrations,
)
from qsou_data.schema import metadata
from qsou_data.search_index import (
    ElasticsearchIndex,
    INDEX_MAPPINGS,
    normalize_index_date,
)
from qsou_data.store import DataAssetStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "api-gateway"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.elasticsearch_service import ElasticsearchService


class PostgresOnlyCatalogTest(unittest.TestCase):
    def test_catalog_rejects_non_postgres_urls(self):
        with self.assertRaisesRegex(CatalogConfigurationError, "只支持 PostgreSQL"):
            _postgres_url("sqlite:///catalog.sqlite3")

    def test_authoritative_schema_compiles_for_postgres(self):
        statements = []
        engine = create_mock_engine(
            "postgresql+psycopg://user:password@database/catalog",
            lambda sql, *_args, **_kwargs: statements.append(str(sql.compile(dialect=engine.dialect))),
        )
        metadata.create_all(engine)
        rendered = "\n".join(statements).lower()
        for table in (
            "raw_objects",
            "standard_documents",
            "document_evidence",
            "processing_outbox",
            "adapter_runs",
            "source_cursors",
            "adapter_run_requests",
        ):
            self.assertIn(f"create table {table}", rendered)
        self.assertNotIn("sqlite", rendered)

    def test_alembic_offline_sql_renders_final_postgres_schema(self):
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        output = io.StringIO()
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:password@database/qsou"},
        ), redirect_stdout(output):
            command.upgrade(config, "head", sql=True)
        rendered = output.getvalue().lower()
        self.assertIn("create table raw_objects", rendered)
        self.assertIn("create table standard_documents", rendered)
        self.assertIn("insert into alembic_version", rendered)

    def test_generic_snapshot_quarantine_parameterizes_like_pattern(self):
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

        self.assertEqual(store.quarantine_generic_snapshots(), 0)
        self.assertIn("parser_version LIKE %s", calls[0][0])
        self.assertEqual(calls[0][1], ("qsou-generic-html/%",))

    def test_runtime_writers_require_completed_external_migrations(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"QSOU_OBJECT_STORAGE_BACKEND": "s3"},
        ):
            root = Path(directory)
            (root / "catalog.sqlite3").touch()
            self.assertEqual(
                required_migrations(root),
                {
                    "schema": ALEMBIC_REVISION,
                    "catalog": SQLITE_IMPORT_VERSION,
                    "objects": OBJECT_IMPORT_VERSION,
                },
            )

            class Result:
                def __init__(self, one=None, all_rows=None):
                    self.one = one
                    self.all_rows = all_rows or []

                def fetchone(self):
                    return self.one

                def fetchall(self):
                    return self.all_rows

            class Connection:
                def execute(self, sql):
                    if "alembic_version" in sql:
                        return Result({"version_num": ALEMBIC_REVISION})
                    return Result(all_rows=[{"version": SQLITE_IMPORT_VERSION}])

            class Context:
                def __enter__(self):
                    return Connection()

                def __exit__(self, *_args):
                    return False

            class Store:
                @staticmethod
                def _connection():
                    return Context()

            store = Store()
            store.root = root
            state = migration_state(store)
            self.assertEqual(state["status"], "waiting")
            self.assertEqual(state["missing"], ["objects"])


class ProductionComposeContractTest(unittest.TestCase):
    def test_postgres_and_elasticsearch_are_required_runtime_services(self):
        compose = yaml.safe_load((PROJECT_ROOT / "compose.yml").read_text())
        services = compose["services"]
        self.assertEqual(
            set(services),
            {"api", "web", "collector", "indexer", "elasticsearch"},
        )
        for service in services.values():
            self.assertEqual(service.get("platform"), "linux/amd64")
        for name in ("api", "collector", "indexer"):
            environment = services[name]["environment"]
            self.assertEqual(environment["DATABASE_URL"], "${DATABASE_URL:?DATABASE_URL is required}")
            self.assertNotIn("QSOU_CATALOG_BACKEND", environment)
            self.assertNotIn("QSOU_MIGRATION_PHASE", environment)
            self.assertNotIn("QSOU_SQLITE_WRITES_FROZEN", environment)
        self.assertEqual(services["api"]["environment"]["ENABLE_ELASTICSEARCH"], "true")
        self.assertEqual(services["api"]["environment"]["ENABLE_QDRANT"], "false")
        self.assertEqual(
            services["api"]["depends_on"]["elasticsearch"]["condition"],
            "service_healthy",
        )
        self.assertEqual(
            services["indexer"]["depends_on"]["elasticsearch"]["condition"],
            "service_healthy",
        )
        self.assertEqual(
            services["indexer"]["build"],
            {"context": ".", "dockerfile": "deploy/api.Dockerfile"},
        )
        self.assertEqual(
            services["indexer"]["command"],
            ["python", "-m", "qsou_data.indexer"],
        )
        self.assertNotIn("image", services["indexer"])
        self.assertNotIn("healthcheck", services["indexer"])
        self.assertIn("qsou-elasticsearch-data", compose["volumes"])
        self.assertEqual(
            services["elasticsearch"]["image"],
            "docker.elastic.co/elasticsearch/elasticsearch:8.11.0",
        )
        self.assertNotIn("build", services["elasticsearch"])
        self.assertEqual(services["elasticsearch"]["restart"], "unless-stopped")
        self.assertNotIn("ports", services["elasticsearch"])
        self.assertEqual(set(services["web"]["ports"]), {"${QSOU_WEB_PORT:-3000}:3000"})
        self.assertIn(
            "http://localhost:8000/live",
            services["api"]["healthcheck"]["test"][-1],
        )

    def test_release_context_excludes_runtime_and_removes_retired_entrypoints(self):
        ignored = set((PROJECT_ROOT / ".dockerignore").read_text().splitlines())
        self.assertIn(".solopreneur", ignored)
        self.assertIn(".playwright-cli", ignored)
        self.assertIn(".pytest_cache", ignored)
        self.assertFalse((PROJECT_ROOT / "qsou_data/migrate.py").exists())
        self.assertFalse((PROJECT_ROOT / "qsou_data/start_api.py").exists())

    def test_api_image_contains_indexer_runtime_dependencies(self):
        def package_names(path):
            return {
                line.split("==", 1)[0].split("[", 1)[0].lower()
                for line in path.read_text().splitlines()
                if line and not line.startswith("#")
            }

        api_packages = package_names(PROJECT_ROOT / "deploy/requirements-api.txt")
        indexer_packages = package_names(PROJECT_ROOT / "deploy/requirements-indexer.txt")
        self.assertTrue(indexer_packages <= api_packages)


class ElasticsearchProjectionTest(unittest.TestCase):
    def test_health_check_reconnects_after_elasticsearch_starts(self):
        service = ElasticsearchService()
        service.connect = AsyncMock(return_value=True)
        health = __import__("asyncio").run(service.health_check())
        self.assertEqual(health["status"], "connected")
        service.connect.assert_awaited_once()

    def test_search_hides_inactive_document_versions(self):
        body = ElasticsearchService()._build_search_query("政策")
        filters = body["query"]["bool"]["filter"]
        self.assertIn({"term": {"active": True}}, filters)

    def test_projection_carries_visibility_and_provenance(self):
        index = ElasticsearchIndex.__new__(ElasticsearchIndex)
        index.alias = "qsou_documents"
        action = index._action(
            {
                "content_version_id": "version-1",
                "canonical_document_id": "document-1",
                "title": "监管政策发布",
                "content": "监管机构发布新的经济政策。",
                "source_id": "government-source",
                "source": "政府公开数据",
                "url": "https://example.gov/policy/1",
                "raw_object_id": "raw-1",
                "active": False,
            }
        )
        self.assertEqual(action["_id"], "version-1")
        self.assertEqual(action["_source"]["raw_object_id"], "raw-1")
        self.assertFalse(action["_source"]["active"])
        self.assertEqual(INDEX_MAPPINGS["properties"]["active"]["type"], "boolean")

    def test_projection_normalizes_source_dates_and_nul_text(self):
        self.assertEqual(
            normalize_index_date("20260807T00:00:00Z"),
            "2026-08-07T00:00:00+00:00",
        )
        self.assertEqual(
            normalize_index_date("2026-08-10 00:00:00.0"),
            "2026-08-10T00:00:00",
        )
        self.assertIsNone(normalize_index_date("not-a-date"))

        index = ElasticsearchIndex.__new__(ElasticsearchIndex)
        index.alias = "qsou_documents"
        action = index._action(
            {
                "content_version_id": "version-1",
                "title": "公告",
                "content": "含有\x00控制符",
                "source_published_at": "20260807T00:00:00Z",
                "fetched_at": "2026-08-09T00:00:00+00:00",
            }
        )
        self.assertNotIn("\x00", action["_source"]["content"])
        self.assertEqual(
            action["_source"]["published_at"],
            "2026-08-07T00:00:00+00:00",
        )

    def test_bulk_failure_reports_rejected_document_reason(self):
        index = ElasticsearchIndex.__new__(ElasticsearchIndex)
        index.alias = "qsou_documents"
        index.client = object()
        rejected = {
            "index": {
                "_id": "version-1",
                "status": 400,
                "error": {
                    "type": "document_parsing_exception",
                    "reason": "failed to parse field [published_at]",
                },
            }
        }
        with patch(
            "qsou_data.search_index.helpers.streaming_bulk",
            return_value=iter([(False, rejected)]),
        ), self.assertRaisesRegex(
            RuntimeError,
            "version-1.*published_at",
        ):
            index.index_documents([{"content_version_id": "version-1"}])

    def test_cycle_reconciles_all_versions_without_rewriting_outbox_state(self):
        class Store:
            marked = []
            pending_batches = iter(
                [[{"content_version_id": "current", "active": True}], [], []]
            )

            @staticmethod
            def documents_for_index():
                return iter([{"content_version_id": "old", "active": False}])

            @staticmethod
            def pending_documents_for_index(_limit):
                return next(Store.pending_batches)

            @staticmethod
            def active_document_count():
                return 1

            @classmethod
            def mark_indexed(cls, ids):
                cls.marked.append(list(ids))

        class Index:
            batches = []
            generations = []
            stale_deletes = []
            refreshes = 0

            @staticmethod
            def ensure_ready():
                return None

            @classmethod
            def index_documents(cls, documents, *, projection_generation=None):
                ids = [document["content_version_id"] for document in documents]
                cls.batches.append(ids)
                cls.generations.append(projection_generation)
                return ids

            @classmethod
            def delete_stale(cls, projection_generation):
                cls.stale_deletes.append(projection_generation)
                return 2

            @classmethod
            def refresh(cls):
                cls.refreshes += 1

            @staticmethod
            def active_document_count():
                return 1

        last_reconcile, result = run_cycle(
            Store(),
            Index(),
            last_reconcile=0,
            reconcile_seconds=3600,
            batch_size=100,
            now=3601,
        )
        self.assertEqual(last_reconcile, 3601)
        self.assertEqual(
            result,
            {
                "reconciled": 1,
                "indexed": 1,
                "active_documents": 1,
                "indexed_active_documents": 1,
                "pending_documents": 0,
                "converged": True,
            },
        )
        self.assertEqual(Index.batches, [["old"], ["current"]])
        self.assertIsNotNone(Index.generations[0])
        self.assertIsNone(Index.generations[1])
        self.assertEqual(Index.stale_deletes, [Index.generations[0]])
        self.assertEqual(Store.marked, [["old"], ["current"]])
        self.assertEqual(Index.refreshes, 2)

    def test_cycle_treats_concurrent_collection_as_catching_up(self):
        class Store:
            active_counts = iter([1, 2])
            pending_batches = iter(
                [
                    [{"content_version_id": "current", "active": True}],
                    [],
                    [{"content_version_id": "next", "active": True}],
                ]
            )

            @staticmethod
            def pending_documents_for_index(_limit):
                return next(Store.pending_batches)

            @staticmethod
            def active_document_count():
                return next(Store.active_counts)

            @staticmethod
            def mark_indexed(_ids):
                return None

        class Index:
            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(documents, *, projection_generation=None):
                self.assertIsNone(projection_generation)
                return [document["content_version_id"] for document in documents]

            @staticmethod
            def refresh():
                return None

            @staticmethod
            def active_document_count():
                return 1

        _, result = run_cycle(
            Store(),
            Index(),
            last_reconcile=100,
            reconcile_seconds=3600,
            batch_size=100,
            now=101,
        )
        self.assertFalse(result["converged"])
        self.assertEqual(result["active_documents"], 2)
        self.assertEqual(result["indexed_active_documents"], 1)
        self.assertEqual(result["pending_documents"], 1)

    def test_cycle_repairs_stable_projection_count_mismatch(self):
        class Store:
            marked = []

            @staticmethod
            def pending_documents_for_index(_limit):
                return []

            @staticmethod
            def active_document_count():
                return 2

            @staticmethod
            def documents_for_index():
                return iter(
                    [
                        {"content_version_id": "one", "active": True},
                        {"content_version_id": "two", "active": True},
                    ]
                )

            @classmethod
            def mark_indexed(cls, ids):
                cls.marked.append(list(ids))

        class Index:
            counts = iter([1, 2])

            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(documents, *, projection_generation=None):
                self.assertIsNotNone(projection_generation)
                return [document["content_version_id"] for document in documents]

            @staticmethod
            def delete_stale(_generation):
                return 0

            @staticmethod
            def refresh():
                return None

            @staticmethod
            def active_document_count():
                return next(Index.counts)

        last_reconcile, result = run_cycle(
            Store(),
            Index(),
            last_reconcile=100,
            reconcile_seconds=3600,
            batch_size=100,
            now=101,
        )
        self.assertEqual(last_reconcile, 101)
        self.assertEqual(result["reconciled"], 2)
        self.assertTrue(result["converged"])
        self.assertEqual(result["active_documents"], 2)
        self.assertEqual(result["indexed_active_documents"], 2)
        self.assertEqual(Store.marked, [["one", "two"]])

    def test_cycle_rejects_mismatch_that_survives_full_repair(self):
        class Store:
            @staticmethod
            def pending_documents_for_index(_limit):
                return []

            @staticmethod
            def active_document_count():
                return 2

            @staticmethod
            def documents_for_index():
                return iter([{"content_version_id": "one", "active": True}])

            @staticmethod
            def mark_indexed(_ids):
                return None

        class Index:
            @staticmethod
            def ensure_ready():
                return None

            @staticmethod
            def index_documents(documents, *, projection_generation=None):
                self.assertIsNotNone(projection_generation)
                return [document["content_version_id"] for document in documents]

            @staticmethod
            def delete_stale(_generation):
                return 0

            @staticmethod
            def refresh():
                return None

            @staticmethod
            def active_document_count():
                return 1

        with self.assertRaisesRegex(
            RuntimeError,
            "postgres=2, elasticsearch=1",
        ):
            run_cycle(
                Store(),
                Index(),
                last_reconcile=100,
                reconcile_seconds=3600,
                batch_size=100,
                now=101,
            )

    def test_indexer_readiness_requires_fresh_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"QSOU_DATA_ROOT": directory},
        ):
            self.assertEqual(read_indexer_state()["status"], "unavailable")
            written = write_indexer_state("healthy", reconciled=3, indexed=1)
            self.assertEqual(written["state"], "healthy")
            current = read_indexer_state(max_age_seconds=30)
            self.assertEqual(current["status"], "healthy")
            payload = json.loads((Path(directory) / "indexer-status.json").read_text())
            self.assertEqual(payload["reconciled"], 3)


if __name__ == "__main__":
    unittest.main()
