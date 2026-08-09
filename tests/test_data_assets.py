import json
import tempfile
import unittest
from pathlib import Path

from qsou_data import DataAssetError, DataAssetStore, SourceRegistry


class DataAssetStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.registry = SourceRegistry(Path(__file__).resolve().parents[1] / "config" / "sources.json")
        self.store = DataAssetStore(root=self.root / "data", registry=self.registry)

    def tearDown(self):
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
