import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qsou_data import DataAssetError, DataAssetStore, SourceRegistry


_test_database_url = os.getenv("QSOU_TEST_DATABASE_URL", "").strip()


@unittest.skipUnless(
    _test_database_url,
    "需要通过 QSOU_TEST_DATABASE_URL 提供隔离的 PostgreSQL 验收库",
)
class DataAssetStoreTest(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {"DATABASE_URL": _test_database_url},
        )
        self.environment.start()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.registry = SourceRegistry(Path(__file__).resolve().parents[1] / "config" / "sources.json")
        self.store = DataAssetStore(root=self.root / "data", registry=self.registry)

    def tearDown(self):
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_raw_evidence_is_immutable_idempotent_and_filters_sensitive_headers(self):
        first = self.store.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/100?utm_source=test",
            status_code=200,
            response_headers={
                b"Content-Type": b"text/html; charset=utf-8",
                b"ETag": b"version-1",
                b"Set-Cookie": b"secret=value",
                b"Authorization": b"Bearer secret",
            },
            body="第一财经原始页面".encode("utf-8"),
            fetched_at="2026-08-08T08:00:00Z",
            content_type="text/html; charset=utf-8",
            encoding="utf-8",
        )
        second = self.store.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/100",
            status_code=200,
            response_headers={b"Content-Type": b"text/html; charset=utf-8"},
            body="第一财经原始页面".encode("utf-8"),
            fetched_at="2026-08-08T08:01:00Z",
            content_type="text/html; charset=utf-8",
            encoding="utf-8",
        )

        self.assertEqual(first["raw_object_id"], second["raw_object_id"])
        stored = self.store.get_evidence(first["raw_object_id"])
        self.assertEqual(stored["fetch_count"], 2)
        self.assertEqual(stored["url"], "https://www.yicai.com/news/100")
        self.assertEqual(stored["response_headers"]["etag"], "version-1")
        self.assertNotIn("set-cookie", stored["response_headers"])
        self.assertNotIn("authorization", stored["response_headers"])
        self.assertEqual(self.store.evidence_body_path(first["raw_object_id"]).read_bytes(), "第一财经原始页面".encode("utf-8"))

    def test_document_versions_keep_first_seen_and_search_the_active_version(self):
        evidence_v1 = self._archive("旧版正文")
        version_v1 = self.store.register_document(
            self._document(evidence_v1, "公司发布年度报告", "旧版正文，营业收入增长。")
        )
        evidence_v2 = self._archive("新版正文")
        version_v2 = self.store.register_document(
            self._document(evidence_v2, "公司发布年度报告", "新版正文，营业收入增长并提高分红。")
        )

        self.assertEqual(version_v1["canonical_document_id"], version_v2["canonical_document_id"])
        self.assertNotEqual(version_v1["content_version_id"], version_v2["content_version_id"])
        self.assertEqual(version_v1["first_seen_at"], version_v2["first_seen_at"])

        result = self.store.search_documents("提高分红")
        self.assertEqual(result["total_count"], 1)
        self.assertEqual(result["results"][0]["id"], version_v2["content_version_id"])
        self.assertEqual(result["results"][0]["raw_object_id"], evidence_v2["raw_object_id"])

        status = self.store.status()
        self.assertEqual(status["raw_objects"], 2)
        self.assertEqual(status["document_versions"], 2)
        self.assertEqual(status["active_documents"], 1)

        # 来源恢复到历史内容时，既有版本应重新成为当前版本，不能留下零个活动文档。
        restored_v1 = self.store.register_document(
            self._document(evidence_v1, "公司发布年度报告", "旧版正文，营业收入增长。")
        )
        self.assertEqual(restored_v1["content_version_id"], version_v1["content_version_id"])
        self.assertEqual(self.store.search_documents("旧版正文")["total_count"], 1)
        self.assertEqual(self.store.status()["active_documents"], 1)

    def test_outbox_replay_and_open_export_preserve_provenance(self):
        evidence = self._archive("可回放正文")
        document = self.store.register_document(
            self._document(evidence, "监管公告发布", "可回放正文，包含明确监管事项。")
        )

        pending = self.store.pending_documents()
        self.assertEqual([item["content_version_id"] for item in pending], [document["content_version_id"]])

        self.store.mark_dispatched([document["content_version_id"]], "task-1")
        self.assertEqual(self.store.pending_documents(), [])
        self.assertEqual(self.store.requeue(source_id="yicai"), 1)
        self.assertEqual(len(self.store.pending_documents()), 1)

        self.store.mark_processing([document["content_version_id"]])
        self.store.mark_processed([document["content_version_id"]])
        self.store.mark_indexed([document["content_version_id"]])
        stored = self.store.get_document(document["content_version_id"])
        self.assertIsNotNone(stored["processed_at"])
        self.assertIsNotNone(stored["indexed_at"])

        exported = list(self.store.export_documents())
        self.assertEqual(exported[0]["raw_object_id"], evidence["raw_object_id"])
        self.assertEqual(exported[0]["source_id"], "yicai")
        self.assertIsNotNone(exported[0]["processed_at"])
        self.assertIsNotNone(exported[0]["indexed_at"])
        json.dumps(exported, ensure_ascii=False)

    def test_same_standard_version_keeps_all_raw_evidence_links(self):
        first_evidence = self._archive("带页面装饰的原始响应 A")
        second_evidence = self._archive("带页面装饰的原始响应 B")
        first = self.store.register_document(
            self._document(first_evidence, "相同标准内容", "相同标准正文，长度满足正式文档要求。")
        )
        second = self.store.register_document(
            self._document(second_evidence, "相同标准内容", "相同标准正文，长度满足正式文档要求。")
        )

        self.assertEqual(first["content_version_id"], second["content_version_id"])
        stored = self.store.get_document(first["content_version_id"])
        self.assertEqual(
            set(stored["raw_object_ids"]),
            {first_evidence["raw_object_id"], second_evidence["raw_object_id"]},
        )

    def test_document_without_archived_evidence_is_rejected(self):
        with self.assertRaises(DataAssetError):
            self.store.register_document(
                {
                    "id": "missing-evidence",
                    "title": "缺少证据的文档",
                    "content": "这条内容不能进入正式数据资产。",
                    "url": "https://www.yicai.com/news/missing",
                    "source_id": "yicai",
                }
            )

    def test_status_reports_observed_collector_state(self):
        status_path = self.root / "data" / "collector-status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            json.dumps({"state": "idle", "last_finished_at": "2026-08-09T02:00:00Z"}),
            encoding="utf-8",
        )
        status = self.store.status()
        self.assertEqual(status["collector"]["state"], "idle")
        self.assertEqual(status["collector"]["last_finished_at"], "2026-08-09T02:00:00Z")

    def test_archived_html_can_become_a_searchable_snapshot(self):
        import sys

        crawler_path = str(Path(__file__).resolve().parents[1] / "crawler")
        sys.path.insert(0, crawler_path)
        try:
            from index_evidence import index_pending_html_evidence
        finally:
            sys.path.remove(crawler_path)

        evidence = self.store.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/example",
            status_code=200,
            response_headers={b"Content-Type": b"text/html; charset=utf-8"},
            content_type="text/html; charset=utf-8",
            encoding="utf-8",
            body=(
                "<html><head><title>上市公司季度经营数据</title></head>"
                "<body><article><h1>上市公司季度经营数据</h1>"
                "<p>公司本季度营业收入保持增长，经营现金流改善，核心业务订单稳定。"
                "管理层同时披露下一季度将继续控制资本开支并提升交付效率，"
                "相关经营数据已经过董事会审阅并向投资者公开。</p>"
                "</article></body></html>"
            ).encode("utf-8"),
        )

        result = index_pending_html_evidence(self.store)
        search = self.store.search_documents("经营现金流")

        self.assertEqual(result["indexed"], 1)
        self.assertEqual(search["total_count"], 1)
        self.assertEqual(search["results"][0]["raw_object_id"], evidence["raw_object_id"])

    def test_adapter_run_records_real_stage_metrics_and_advances_cursor_only_when_healthy(self):
        run = self.store.begin_adapter_run(
            source_id="yicai",
            adapter_id="yicai-news",
            adapter_version="1.2.0",
        )
        finished = self.store.finish_adapter_run(
            run["run_id"],
            state="healthy",
            metrics={
                "entrypoints_total": 1,
                "entrypoints_succeeded": 1,
                "detail_discovered": 5,
                "detail_fetched": 4,
                "documents_emitted": 3,
                "documents_indexed": 3,
                "evidence_archived": 5,
                "failures": 1,
            },
            cursor={"latest_published_at": "2026-08-08T09:00:00+08:00"},
        )

        self.assertEqual(finished["state"], "healthy")
        self.assertEqual(finished["detail_discovered"], 5)
        self.assertEqual(
            self.store.get_source_cursor("yicai")["latest_published_at"],
            "2026-08-08T09:00:00+08:00",
        )
        source = next(item for item in self.store.list_sources() if item["source_id"] == "yicai")
        self.assertEqual(source["collection_state"], "healthy")
        self.assertEqual(source["last_run"]["documents_emitted"], 3)
        self.assertEqual(source["last_run"]["metrics"]["documents_indexed"], 3)

    def test_manual_adapter_requests_are_deduplicated_claimed_and_closed(self):
        first = self.store.request_adapter_run("sse", requested_by="admin")
        duplicate = self.store.request_adapter_run("sse", requested_by="admin")

        self.assertEqual(first["request_id"], duplicate["request_id"])
        self.assertEqual(first["state"], "queued")
        source = next(item for item in self.store.list_sources() if item["source_id"] == "sse")
        self.assertEqual(source["collection_state"], "queued")

        claimed = self.store.claim_adapter_run_request()
        self.assertEqual(claimed["request_id"], first["request_id"])
        self.assertEqual(claimed["state"], "running")

        closed = self.store.finish_adapter_run_request(
            first["request_id"],
            run_id="run-1",
            result_state="healthy",
        )
        self.assertEqual(closed["state"], "completed")
        self.assertEqual(closed["result_state"], "healthy")
        self.assertIsNone(self.store.active_adapter_run_request("sse"))

    def test_generic_snapshots_are_preserved_but_removed_from_formal_search(self):
        evidence = self._archive("通用快照原始页面")
        document = self.store.register_document(
            {
                **self._document(evidence, "通用入口页面快照", "通用入口页面快照正文，不能替代来源适配器产生的正式情报文档。"),
                "parser_version": "qsou-generic-html/1",
            }
        )
        self.store.mark_indexed([document["content_version_id"]])

        self.assertEqual(self.store.search_documents("通用入口页面")["total_count"], 1)
        self.assertEqual(self.store.quarantine_generic_snapshots(), 1)
        self.assertEqual(self.store.search_documents("通用入口页面")["total_count"], 0)
        self.assertEqual(len(list(self.store.export_documents())), 1)

    def _archive(self, body: str):
        return self.store.archive_response(
            source_id="yicai",
            url="https://www.yicai.com/news/annual-report",
            status_code=200,
            response_headers={b"Content-Type": b"text/html"},
            body=body.encode("utf-8"),
            fetched_at="2026-08-08T08:00:00Z" if body == "旧版正文" else "2026-08-08T09:00:00Z",
            content_type="text/html",
            encoding="utf-8",
        )

    @staticmethod
    def _document(evidence, title: str, content: str):
        return {
            "id": "annual-report-2026",
            "type": "announcement",
            "title": title,
            "content": content,
            "url": "https://www.yicai.com/news/annual-report",
            "source": "第一财经",
            "source_id": "yicai",
            "raw_object_id": evidence["raw_object_id"],
            "source_published_at": "2026-08-08T07:30:00Z",
            "fetched_at": evidence["last_fetched_at"],
            "parser_version": "test/1",
        }


if __name__ == "__main__":
    unittest.main()
