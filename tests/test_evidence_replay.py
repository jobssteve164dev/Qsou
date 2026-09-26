import json
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CRAWLER_ROOT = PROJECT_ROOT / "crawler"
if str(CRAWLER_ROOT) not in sys.path:
    sys.path.insert(0, str(CRAWLER_ROOT))

from qsou_crawler.adapters import DocumentReference, ResponsePayload
from qsou_crawler.adapters.registry import AdapterRegistry
from replay_evidence import replay_evidence_batch


class RecordingStore:
    def __init__(self, root: Path, evidence: list[dict]):
        self.root = root
        self.registry = None
        self._evidence = list(evidence)
        self.documents = []
        self.completed = []

    def claim_evidence_replay(self, limit):
        return self._evidence[:limit]

    def evidence_body_path(self, raw_object_id):
        return self.root / f"{raw_object_id}.body"

    def evidence_has_document(self, _raw_object_id):
        return False

    def effective_source(self, source_id):
        return {"source_id": source_id}

    def register_document(self, document):
        self.documents.append(document)
        return {**document, "content_version_id": f"version-{len(self.documents)}"}

    def complete_evidence_replay(self, raw_object_id, state, error=None):
        self.completed.append((raw_object_id, state, error))


class FakeAdapter:
    source_id = "test-source"
    document_type = "news"

    @staticmethod
    def reference_id(url):
        return url.rsplit("/", 1)[-1]

    def accepts_detail_url(self, _url):
        return True

    def discover(self, _response):
        return []

    def parse_document(self, response, reference):
        if response.body == b"broken":
            raise ValueError("broken fixture")
        return {
            "source_document_id": reference.source_document_id,
            "type": reference.document_type,
            "title": reference.title,
            "content": "A complete archived article body with enough content for processing. " * 2,
            "url": response.url,
            "source_id": self.source_id,
            "parser_version": "test/1",
            "metadata": dict(reference.metadata),
        }


class FakeRegistry:
    def create(self, _source_id, _source=None):
        return FakeAdapter()


class DetailOnlyAdapter(FakeAdapter):
    def discover(self, _response):
        raise ValueError("detail payload is not a listing")


class DetailOnlyRegistry:
    def create(self, _source_id, _source=None):
        return DetailOnlyAdapter()


class EvidenceReplayTest(unittest.TestCase):
    def _evidence(self, raw_object_id, *, body, context=None):
        path = self.root / f"{raw_object_id}.body"
        path.write_bytes(body)
        return {
            "raw_object_id": raw_object_id,
            "source_id": "test-source",
            "url": f"https://example.com/{raw_object_id}",
            "status_code": 200,
            "content_type": "text/html; charset=utf-8",
            "encoding": "utf-8",
            "last_fetched_at": "2026-09-26T00:00:00Z",
            "request_context": context or {},
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_detail_replay_restores_persisted_document_identity(self):
        evidence = self._evidence(
            "detail",
            body=b"article",
            context={
                "qsou_request_kind": "detail",
                "source_document_id": "source-article-42",
                "title": "Archived source title",
                "published_at": "2026-09-25T08:00:00Z",
                "document_type": "news",
                "company_code": "600000",
            },
        )
        store = RecordingStore(self.root, [evidence])

        result = replay_evidence_batch(store, FakeRegistry(), batch_size=10)

        self.assertEqual(result, {"claimed": 1, "parsed": 1, "skipped": 0, "failed": 0})
        self.assertEqual(store.documents[0]["source_document_id"], "source-article-42")
        self.assertEqual(store.documents[0]["raw_object_id"], "detail")
        self.assertEqual(store.documents[0]["metadata"]["company_code"], "600000")
        self.assertEqual(store.completed, [("detail", "parsed", None)])

    def test_one_malformed_evidence_does_not_block_the_next_document(self):
        first = self._evidence(
            "broken",
            body=b"broken",
            context={"qsou_request_kind": "detail", "title": "Broken article"},
        )
        second = self._evidence(
            "healthy",
            body=b"article",
            context={"qsou_request_kind": "detail", "title": "Healthy article"},
        )
        store = RecordingStore(self.root, [first, second])

        result = replay_evidence_batch(store, FakeRegistry(), batch_size=10)

        self.assertEqual(result, {"claimed": 2, "parsed": 1, "skipped": 0, "failed": 1})
        self.assertEqual(store.documents[0]["raw_object_id"], "healthy")
        self.assertEqual(store.completed[0][0:2], ("broken", "failed"))
        self.assertIn("broken fixture", store.completed[0][2])
        self.assertEqual(store.completed[1], ("healthy", "parsed", None))

    def test_historical_detail_without_request_context_uses_its_detail_adapter(self):
        evidence = self._evidence("legacy-detail", body=b"article")
        store = RecordingStore(self.root, [evidence])

        result = replay_evidence_batch(store, DetailOnlyRegistry(), batch_size=10)

        self.assertEqual(result["parsed"], 1)
        self.assertEqual(store.documents[0]["source_document_id"], "legacy-detail")

    def test_archived_inline_official_response_uses_the_real_source_adapter(self):
        payload = [
            {"lastupdated": "2026-09-25"},
            [
                {
                    "country": {"value": "China"},
                    "indicator": {"value": "GDP"},
                    "date": "2025",
                    "value": 123,
                }
            ],
        ]
        body = json.dumps(payload).encode("utf-8")
        evidence = self._evidence("world-bank", body=body)
        evidence.update(
            {
                "source_id": "world-bank",
                "url": "https://api.worldbank.org/v2/country/CHN/indicator/NY.GDP.MKTP.CD?format=json",
                "content_type": "application/json",
            }
        )
        store = RecordingStore(self.root, [evidence])
        store.registry = AdapterRegistry().sources

        result = replay_evidence_batch(store, AdapterRegistry(), batch_size=10)

        self.assertEqual(result["parsed"], 1)
        self.assertEqual(store.documents[0]["source_document_id"], "WDI-NY.GDP.MKTP.CD-CHN")
        self.assertEqual(store.documents[0]["raw_object_id"], "world-bank")

    def test_historical_sec_filing_without_context_is_replayed_by_real_adapter(self):
        body = (
            "<html><body><main><h1>NVIDIA CORP 10-K filing</h1>"
            "<p>This complete submission reports revenue, cash flow, assets, liabilities, "
            "risk factors, operations, and audited financial statements for the fiscal year.</p>"
            "</main></body></html>"
        ).encode("utf-8")
        evidence = self._evidence("sec-filing", body=body)
        evidence.update(
            {
                "source_id": "sec-edgar",
                "url": "https://www.sec.gov/Archives/edgar/data/1045810/0001045810-26-000123.txt",
                "content_type": "text/plain; charset=utf-8",
            }
        )
        store = RecordingStore(self.root, [evidence])
        store.registry = AdapterRegistry().sources

        result = replay_evidence_batch(store, AdapterRegistry(), batch_size=10)

        self.assertEqual(result["parsed"], 1)
        self.assertEqual(
            store.documents[0]["source_document_id"],
            "0001045810-26-000123",
        )
        self.assertEqual(store.documents[0]["raw_object_id"], "sec-filing")

    def test_historical_nbs_release_keeps_the_discovered_document_identity(self):
        registry = AdapterRegistry()
        adapter = registry.create("nbs")
        url = "https://www.stats.gov.cn/sj/zxfb/202609/t20260901_123.html"
        listing = ResponsePayload(
            url="https://www.stats.gov.cn/sj/zxfb/",
            body=f'<a href="{url}">2026年8月份国民经济运行情况</a>'.encode(),
        )
        expected_id = adapter.discover(listing)[0].source_document_id
        body = (
            "<html><head><title>2026年8月份国民经济运行情况</title></head><body>"
            '<div class="TRS_Editor"><p>8月份，国民经济运行总体平稳，生产需求持续恢复，'
            "转型升级稳步推进，高质量发展成色更足。</p></div></body></html>"
        ).encode()
        evidence = self._evidence("nbs-release", body=body)
        evidence.update({"source_id": "nbs", "url": url})
        store = RecordingStore(self.root, [evidence])
        store.registry = registry.sources

        result = replay_evidence_batch(store, registry, batch_size=10)

        self.assertEqual(result["parsed"], 1)
        self.assertEqual(expected_id, "20260901-123")
        self.assertEqual(store.documents[0]["source_document_id"], expected_id)

    def test_collector_cycle_automatically_advances_archived_evidence(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:password@database/qsou"},
        ):
            run_schedule = importlib.import_module("run_schedule")
        evidence = self._evidence(
            "scheduled",
            body=b"article",
            context={"qsou_request_kind": "detail", "title": "Scheduled article"},
        )
        store = RecordingStore(self.root, [evidence])
        statuses = []

        with (
            patch.object(run_schedule, "STORE", store),
            patch.object(run_schedule, "ADAPTERS", FakeRegistry()),
            patch.object(run_schedule, "run_requested_sources", return_value=0),
            patch.object(run_schedule, "selected_adapters", return_value=[]),
            patch.object(run_schedule, "source_summary", return_value={}),
            patch.object(run_schedule, "wait_until", return_value=None),
            patch.object(
                run_schedule,
                "write_status",
                side_effect=lambda **values: statuses.append(values),
            ),
        ):
            run_schedule.run_due_sources()

        self.assertEqual(store.documents[0]["raw_object_id"], "scheduled")
        self.assertEqual(statuses[-1]["evidence_replay"]["parsed"], 1)


if __name__ == "__main__":
    unittest.main()
