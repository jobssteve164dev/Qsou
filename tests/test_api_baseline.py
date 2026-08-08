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
os.environ["QSOU_DATA_ROOT"] = str(Path(_temporary_directory.name) / "data")
os.environ["QSOU_SOURCE_REGISTRY"] = str(PROJECT_ROOT / "config" / "sources.json")
os.environ["ENABLE_DERIVED_SEARCH"] = "false"
os.environ["ENABLE_DERIVED_PROCESSING"] = "false"
os.environ["ENABLE_METRICS"] = "false"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient

from app.main import app
from qsou_data import DataAssetStore


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

            status = client.get("/api/v1/data/status")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["raw_objects"], 1)
            self.assertEqual(status.json()["active_documents"], 1)

            system_stats = client.get("/api/v1/system/stats")
            self.assertEqual(system_stats.status_code, 200)
            self.assertEqual(system_stats.json()["system_status"], "healthy")
            self.assertEqual(system_stats.json()["service_states"]["data_assets"], "healthy")
            self.assertEqual(system_stats.json()["service_states"]["elasticsearch"], "disabled")
            self.assertEqual(system_stats.json()["service_states"]["qdrant"], "disabled")

            search = client.post(
                "/api/v1/search/",
                json={"query": "自主数据", "search_type": "hybrid", "page": 1, "page_size": 20},
            )
            self.assertEqual(search.status_code, 200)
            self.assertEqual(search.json()["total_count"], 1)
            self.assertEqual(search.json()["results"][0]["id"], document["content_version_id"])

            content = client.get(f"/api/v1/data/evidence/{evidence['raw_object_id']}/content")
            self.assertEqual(content.status_code, 200)
            self.assertEqual(content.content, "Qsou 基线原始证据".encode("utf-8"))

            exported = client.get("/api/v1/data/export")
            self.assertEqual(exported.status_code, 200)
            self.assertIn(document["content_version_id"], exported.text)
            self.assertIn(evidence["raw_object_id"], exported.text)

            replay = client.post("/api/v1/data/replay", json={"source_id": "yicai", "limit": 10})
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.json()["queued_count"], 1)

            unknown_export = client.get("/api/v1/data/export?source_id=not-registered")
            self.assertEqual(unknown_export.status_code, 400)


if __name__ == "__main__":
    unittest.main()
