import json
import sys
import unittest
from pathlib import Path


CRAWLER_ROOT = Path(__file__).resolve().parents[1] / "crawler"
sys.path.insert(0, str(CRAWLER_ROOT))

from qsou_crawler.adapters import AdapterRegistry, DocumentReference, ResponsePayload
from qsou_crawler import settings as crawler_settings


class SourceAdapterContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = AdapterRegistry()

    def test_every_enabled_source_has_exactly_one_versioned_adapter(self):
        catalog = self.registry.catalog()
        self.assertEqual(len(catalog), 9)
        self.assertEqual(len({item["source_id"] for item in catalog}), 9)
        self.assertTrue(all(item["adapter_id"] for item in catalog))
        versions = {item["source_id"]: item["adapter_version"] for item in catalog}
        self.assertEqual(
            versions,
            {
                "sse": "1.1.0",
                "szse": "1.0.0",
                "cninfo": "1.0.0",
                "eastmoney": "1.1.0",
                "sina-finance": "1.1.0",
                "netease-finance": "1.1.0",
                "sec-edgar": "1.0.0",
                "caijing": "1.0.0",
                "yicai": "1.2.0",
            },
        )

    def test_production_crawler_exposes_only_the_versioned_adapter_path(self):
        self.assertEqual(
            crawler_settings.SPIDER_MODULES,
            ["qsou_crawler.spiders.source_adapter_spider"],
        )
        self.assertEqual(
            crawler_settings.DOWNLOADER_MIDDLEWARES,
            {"qsou_crawler.middlewares.RawEvidenceDownloaderMiddleware": 540},
        )
        self.assertEqual(
            crawler_settings.SPIDER_MIDDLEWARES,
            {"qsou_crawler.middlewares.EvidenceLinkMiddleware": 100},
        )
        self.assertEqual(
            list(crawler_settings.ITEM_PIPELINES),
            [
                "qsou_crawler.pipelines.data_processing_pipeline.ValidationPipeline",
                "qsou_crawler.pipelines.data_processing_pipeline.DataProcessingPipeline",
            ],
        )
        self.assertTrue(crawler_settings.ROBOTSTXT_OBEY)
        self.assertIn("qsou.szlk.uk", crawler_settings.USER_AGENT)
        self.assertFalse(crawler_settings.QSOU_OUTBOX_DISPATCH_ENABLED)
        self.assertEqual(crawler_settings.REQUEST_FINGERPRINTER_IMPLEMENTATION, "2.7")
        self.assertGreaterEqual(crawler_settings.DOWNLOAD_TIMEOUT, 900)
        self.assertEqual(crawler_settings.MEMUSAGE_LIMIT_MB, 3584)

    def test_downloader_evidence_identity_stays_on_request_until_spider_stage(self):
        project_root = Path(__file__).resolve().parents[1]
        middleware = (
            project_root / "crawler/qsou_crawler/middlewares.py"
        ).read_text(encoding="utf-8")
        spider = (
            project_root / "crawler/qsou_crawler/spiders/source_adapter_spider.py"
        ).read_text(encoding="utf-8")
        scheduler = (project_root / "crawler/run_schedule.py").read_text(encoding="utf-8")

        self.assertIn('request.meta["qsou_evidence"]', middleware)
        self.assertNotIn('response.meta["qsou_evidence"] =', middleware)
        self.assertIn("errback=self.handle_request_error", spider)
        self.assertNotIn('metadata["handle_httpstatus_all"]', spider)
        self.assertIn('"LOG_FILE="', scheduler)
        self.assertIn('latest.get("adapter_version") != adapter.version', scheduler)
        self.assertGreaterEqual(scheduler.count("run_requested_sources()"), 3)
        self.assertNotIn('("last_started_at", "last_finished_at", "next_run_at")', scheduler)

    def test_collector_image_uses_an_explicit_runtime_allowlist(self):
        project_root = Path(__file__).resolve().parents[1]
        dockerfile = (project_root / "deploy/crawler.Dockerfile").read_text(encoding="utf-8")
        api_dockerfile = (project_root / "deploy/api.Dockerfile").read_text(encoding="utf-8")
        dockerignore = (project_root / ".dockerignore").read_text(encoding="utf-8")
        self.assertNotIn("COPY crawler /app/crawler", dockerfile)
        self.assertIn("source_adapter_spider.py", dockerfile)
        self.assertIn("crawler/qsou_crawler/adapters", dockerfile)
        self.assertIn("pip install --no-cache-dir --no-compile", dockerfile)
        self.assertIn("pip install --no-cache-dir --no-compile", api_dockerfile)
        self.assertIn("crawler/plugins", dockerignore)
        self.assertIn("company_announcement_spider.py", dockerignore)

    def test_primary_announcement_adapters_discover_official_pdf_details(self):
        samples = {
            "sse": {
                "payload": {
                    "pageHelp": {
                        "data": [
                            {
                                "SECURITY_CODE": "600000",
                                "SECURITY_NAME": "浦发银行",
                                "SSEDATE": "2026-08-08",
                                "TITLE": "浦发银行半年度报告",
                                "URL": "/disclosure/listedinfo/announcement/c/new/2026-08-08/600000.pdf",
                                "BULLETIN_TYPE": "半年报",
                            }
                        ]
                    }
                },
                "url": "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
                "expected_host": "big5.sse.com.cn",
                "expected_path": "/site/cht/www.sse.com.cn/disclosure/",
            },
            "szse": {
                "payload": {
                    "data": [
                        {
                            "secCode": "000001",
                            "secName": "平安银行",
                            "announList": [
                                {
                                    "annId": 1001,
                                    "title": "平安银行半年度报告",
                                    "attachPath": "/disc/finalpage/2026-08-08/report.PDF",
                                    "publishTime": "2026-08-08 00:00:00.0",
                                }
                            ],
                        }
                    ]
                },
                "url": "https://www.szse.cn/api/disc/announcement/detailinfo",
                "expected_host": "disc.static.szse.cn",
            },
            "cninfo": {
                "payload": {
                    "announcements": [
                        {
                            "secCode": "000001",
                            "secName": "平安银行",
                            "announcementId": "1002",
                            "announcementTitle": "平安银行股票交易公告",
                            "announcementTime": 1786118400000,
                            "adjunctUrl": "finalpage/2026-08-08/1002.PDF",
                        }
                    ]
                },
                "url": "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                "expected_host": "static.cninfo.com.cn",
            },
        }
        for source_id, sample in samples.items():
            with self.subTest(source_id=source_id):
                adapter = self.registry.create(source_id)
                response = ResponsePayload(
                    url=sample["url"],
                    body=json.dumps(sample["payload"], ensure_ascii=False).encode(),
                    content_type="application/json",
                )
                references = adapter.discover(response)
                self.assertEqual(len(references), 1)
                self.assertIn(sample["expected_host"], references[0].url)
                if sample.get("expected_path"):
                    self.assertIn(sample["expected_path"], references[0].url)
                self.assertEqual(references[0].document_type, "announcement")

    def test_each_news_adapter_discovers_only_its_own_detail_pattern(self):
        links = {
            "eastmoney": "https://finance.eastmoney.com/a/202608081234567890.html",
            "sina-finance": "https://finance.sina.com.cn/stock/marketresearch/2026-08-08/doc-abcdef123456.shtml",
            "netease-finance": "https://www.163.com/money/article/ABCDEFGH00258105.html",
            "caijing": "https://economy.caijing.com.cn/20260808/1234567.shtml",
            "yicai": "https://www.yicai.com/news/102999999.html",
        }
        for source_id, expected_url in links.items():
            with self.subTest(source_id=source_id):
                adapter = self.registry.create(source_id)
                if source_id == "caijing":
                    body = json.dumps(
                        {
                            "data": {
                                "lists": [
                                    {
                                        "contentid": "1234567",
                                        "title": "有效财经详情",
                                        "url": "https://m.caijing.com.cn/json/content/202608/1234567.json",
                                        "published": "1786118400",
                                    }
                                ]
                            }
                        }
                    ).encode()
                else:
                    body = (
                        f'<html><body><a href="{expected_url}">有效财经详情</a>'
                        '<a href="https://example.com/not-allowed">外部链接</a></body></html>'
                    ).encode()
                references = adapter.discover(
                    ResponsePayload(url=adapter.source["entrypoints"][0], body=body)
                )
                expected = (
                    "https://m.caijing.com.cn/json/content/202608/1234567.json"
                    if source_id == "caijing"
                    else expected_url
                )
                self.assertEqual([item.url for item in references], [expected])

    def test_sec_edgar_uses_declared_automated_access_and_daily_master_index(self):
        adapter = self.registry.create("sec-edgar")
        initial = adapter.initial_requests()
        self.assertEqual(len(initial), 1)
        self.assertIn("/Archives/edgar/daily-index/", initial[0].url)
        self.assertIn("QSou", initial[0].headers["User-Agent"])

        quarter = ResponsePayload(
            url="https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/index.json",
            body=json.dumps(
                {
                    "directory": {
                        "item": [
                            {"name": "master.20260806.idx"},
                            {"name": "master.20260807.idx"},
                            {"name": "sitemap.20260807.xml"},
                        ]
                    }
                }
            ).encode(),
            content_type="application/json",
            metadata={"sec_stage": "quarter_index"},
        )
        followups = adapter.listing_requests(quarter)
        self.assertEqual(
            [item.url for item in followups],
            ["https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260807.idx"],
        )

        master = ResponsePayload(
            url=followups[0].url,
            body=(
                "CIK|Company Name|Form Type|Date Filed|Filename\n"
                "1045810|NVIDIA CORP|8-K|2026-08-07|edgar/data/1045810/0001045810-26-000123.txt\n"
                "1045810|NVIDIA CORP|UPLOAD|2026-08-07|edgar/data/1045810/0001045810-26-000124.txt\n"
            ).encode(),
            content_type="text/plain",
            metadata={"sec_stage": "daily_master", "master_index": "master.20260807.idx"},
        )
        references = adapter.discover(master)
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].source_document_id, "0001045810-26-000123")
        self.assertEqual(references[0].metadata["form_type"], "8-K")
        self.assertEqual(references[0].document_type, "filing")

        filing = adapter.parse_document(
            ResponsePayload(
                url=references[0].url,
                body=(
                    "<html><body><main><h1>Current report</h1>"
                    "<p>The registrant announced material operating results and filed the attached disclosure.</p>"
                    "<p>The complete submission preserves the official filing evidence and accession identity.</p>"
                    "</main></body></html>"
                ).encode(),
            ),
            references[0],
        )
        self.assertIsNotNone(filing)
        self.assertEqual(filing["source_id"], "sec-edgar")
        self.assertEqual(filing["parser_version"], "sec-edgar-filings/1.0.0")
        self.assertEqual(filing["metadata"]["accession_number"], "0001045810-26-000123")

    def test_structured_article_parser_emits_provenance_and_version(self):
        adapter = self.registry.create("yicai")
        url = "https://www.yicai.com/news/102999999.html"
        html = (
            "<html><head><meta property='article:published_time' content='2026-08-08T09:00:00+08:00'>"
            "<title>上市公司公布季度经营数据</title></head><body><article>"
            "<h1>上市公司公布季度经营数据</h1>"
            "<p>公司本季度营业收入保持增长，经营现金流明显改善，核心业务订单保持稳定。</p>"
            "<p>管理层同时披露下一季度资本开支计划，并说明主要业务的交付安排与风险因素。</p>"
            "</article></body></html>"
        ).encode()
        document = adapter.parse_document(
            ResponsePayload(url=url, body=html),
            DocumentReference(url=url, source_document_id="102999999", document_type="news"),
        )
        self.assertIsNotNone(document)
        self.assertEqual(document["source_id"], "yicai")
        self.assertEqual(document["parser_version"], "yicai-news/1.2.0")
        self.assertEqual(document["metadata"]["extraction"], "structured_source_adapter")
        self.assertIn("经营现金流", document["content"])

    def test_image_story_preserves_media_without_inventing_ocr_text(self):
        adapter = self.registry.create("yicai")
        url = "https://www.yicai.com/news/103310862.html"
        html = (
            "<html><head><title>晓数点丨明日打新！全方位图解宇树科技IPO</title>"
            "<meta name='description' content='人形机器人第一股来了！'></head><body>"
            "<div class='m-txt'><p><img src='https://imgcdn.yicai.com/a.jpg'></p>"
            "<p><img src='/b.jpg'></p></div></body></html>"
        ).encode()
        document = adapter.parse_document(
            ResponsePayload(url=url, body=html),
            DocumentReference(url=url, source_document_id="103310862", document_type="news"),
        )
        self.assertIsNotNone(document)
        self.assertEqual(document["metadata"]["content_format"], "image_story")
        self.assertEqual(document["metadata"]["media_count"], 2)
        self.assertEqual(
            document["metadata"]["media_urls"],
            ["https://imgcdn.yicai.com/a.jpg", "https://www.yicai.com/b.jpg"],
        )
        self.assertIn("正文由 2 张图片组成", document["content"])
        self.assertNotIn("OCR", document["content"])

    def test_news_adapters_extract_their_article_container_without_navigation(self):
        samples = {
            "eastmoney": ("ContentBody", "https://finance.eastmoney.com/a/202608081234567890.html"),
            "sina-finance": ("artibody", "https://finance.sina.com.cn/stock/doc-abcdef.shtml"),
            "netease-finance": ("post_body", "https://www.163.com/money/article/ABCDEFGH.html"),
            "yicai": ("m-txt", "https://www.yicai.com/news/102999999.html"),
        }
        for source_id, (container, url) in samples.items():
            with self.subTest(source_id=source_id):
                adapter = self.registry.create(source_id)
                html = (
                    "<html><head><meta property='og:title' content='公司经营数据更新'></head><body>"
                    "<nav><p>首页 股票 行情 基金 理财 登录 注册 下载客户端</p></nav>"
                    f"<div class='{container}'><h1>公司经营数据更新</h1>"
                    "<p>公司披露本期营业收入和经营现金流均保持增长，核心业务订单按计划交付。</p>"
                    "<p>公告同时说明了资本开支、市场需求和主要风险，相关数字以原始披露为准，后续变化将继续通过正式公告更新。</p>"
                    "</div><footer><p>关于我们 联系方式 广告服务 用户协议</p></footer>"
                    "</body></html>"
                ).encode()
                document = adapter.parse_document(
                    ResponsePayload(url=url, body=html),
                    DocumentReference(url=url, source_document_id="sample", document_type="news"),
                )
                self.assertIsNotNone(document)
                self.assertIn("营业收入", document["content"])
                self.assertNotIn("下载客户端", document["content"])
                self.assertNotIn("广告服务", document["content"])


if __name__ == "__main__":
    unittest.main()
