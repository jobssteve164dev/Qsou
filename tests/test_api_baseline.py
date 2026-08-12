import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "api-gateway"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

_temporary_directory = tempfile.TemporaryDirectory()
_test_database_url = os.getenv("QSOU_TEST_DATABASE_URL", "").strip()
os.environ["QSOU_DATA_ROOT"] = str(Path(_temporary_directory.name) / "data")
os.environ["QSOU_SOURCE_REGISTRY"] = str(PROJECT_ROOT / "config" / "sources.json")
os.environ["DATABASE_URL"] = _test_database_url or "postgresql://test:test@127.0.0.1:1/qsou_test_unavailable"
os.environ["ENABLE_ELASTICSEARCH"] = "false"
os.environ["ENABLE_QDRANT"] = "false"
os.environ["ENABLE_DERIVED_PROCESSING"] = "false"
os.environ["ENABLE_METRICS"] = "false"
os.environ["DEBUG"] = "false"
os.environ["QSOU_ADMIN_USERNAME"] = "owner"
os.environ["QSOU_ADMIN_PASSWORD"] = "strong-password"
os.environ["SECRET_KEY"] = "test-signing-key"

from fastapi.testclient import TestClient

from app.main import app
from qsou_data import DataAssetStore


@unittest.skipUnless(
    _test_database_url,
    "需要通过 QSOU_TEST_DATABASE_URL 提供隔离的 PostgreSQL 验收库",
)
class BaselineApiTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        _temporary_directory.cleanup()

    def test_health_archive_search_export_and_replay(self):
        store = DataAssetStore()
        evidence = store.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/baseline",
            status_code=200,
            response_headers={"Content-Type": "text/html"},
            body="Qsou 基线原始证据".encode("utf-8"),
            fetched_at="2026-08-08T10:00:00Z",
            content_type="text/html; charset=utf-8",
            encoding="utf-8",
            collector="api-integration-test",
        )
        document = store.register_document(
            {
                "id": "baseline-document",
                "type": "news",
                "title": "自主数据基线完成验证",
                "content": "这是一条可以搜索、追溯、导出和回放的自主数据资产。",
                "url": "https://www.yicai.com/news/baseline",
                "source": "第一财经",
                "source_id": "yicai",
                "raw_object_id": evidence["raw_object_id"],
                "source_published_at": "2026-08-08T09:55:00Z",
                "fetched_at": "2026-08-08T10:00:00Z",
                "parser_version": "api-integration-test/1",
            }
        )

        with TestClient(app) as client:
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "healthy")

            unauthenticated = client.get("/api/v1/data/status")
            self.assertEqual(unauthenticated.status_code, 401)

            login = client.post(
                "/api/v1/auth/login",
                json={"username": "owner", "password": "strong-password"},
            )
            self.assertEqual(login.status_code, 200)
            headers = {"Authorization": f"Bearer {login.json()['token']}"}

            status = client.get("/api/v1/data/status", headers=headers)
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["raw_objects"], 1)
            self.assertEqual(status.json()["active_documents"], 1)
            self.assertGreater(status.json()["archive_size_bytes"], len("Qsou 基线原始证据".encode("utf-8")))
            self.assertEqual(status.json()["registered_sources"], 9)
            self.assertEqual(status.json()["active_sources"], 9)

            trigger = client.post("/api/v1/data/adapter-runs/yicai/trigger", headers=headers)
            self.assertEqual(trigger.status_code, 202)
            duplicate_trigger = client.post("/api/v1/data/adapter-runs/yicai/trigger", headers=headers)
            self.assertEqual(duplicate_trigger.status_code, 202)
            self.assertEqual(
                trigger.json()["request"]["request_id"],
                duplicate_trigger.json()["request"]["request_id"],
            )

            search = client.post(
                "/api/v1/search",
                json={"query": "自主数据", "search_type": "hybrid", "page": 1, "page_size": 20},
                headers=headers,
                follow_redirects=False,
            )
            self.assertEqual(search.status_code, 200)
            self.assertEqual(search.json()["total_count"], 1)
            self.assertEqual(search.json()["results"][0]["id"], document["content_version_id"])

            content = client.get(f"/api/v1/data/evidence/{evidence['raw_object_id']}/content", headers=headers)
            self.assertEqual(content.status_code, 200)
            self.assertEqual(content.content, "Qsou 基线原始证据".encode("utf-8"))

            exported = client.get("/api/v1/data/export", headers=headers)
            self.assertEqual(exported.status_code, 200)
            self.assertIn(document["content_version_id"], exported.text)
            self.assertIn(evidence["raw_object_id"], exported.text)

            replay = client.post("/api/v1/data/replay", json={"source_id": "yicai", "limit": 10}, headers=headers)
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.json()["queued_count"], 1)

            unknown_export = client.get("/api/v1/data/export?source_id=not-registered", headers=headers)
            self.assertEqual(unknown_export.status_code, 400)


if __name__ == "__main__":
    unittest.main()
