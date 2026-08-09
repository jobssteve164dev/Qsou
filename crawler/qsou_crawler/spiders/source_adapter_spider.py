"""One production Spider executing one versioned source adapter."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import scrapy

from qsou_data import DataAssetStore
from qsou_crawler.adapters import AdapterRegistry, DocumentReference, RequestSpec, ResponsePayload


class SourceAdapterSpider(scrapy.Spider):
    name = "source_adapter"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "RANDOMIZE_DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "ROBOTSTXT_OBEY": True,
    }

    def __init__(self, source_id: str, report_path: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.adapter = AdapterRegistry().create(source_id)
        self.source_id = source_id
        self.report_path = Path(report_path) if report_path else None
        self.allowed_domains = list(self.adapter.source.get("domains", []))
        self.max_details = max(1, min(int(os.getenv("QSOU_ADAPTER_MAX_DETAILS", "12")), 100))
        self.asset_store = DataAssetStore()
        self._seen_details: set[str] = set()
        self._documents: list[dict[str, Any]] = []
        self._errors: list[str] = []

    def start_requests(self):
        cursor = self.asset_store.get_source_cursor(self.source_id)
        specifications = self.adapter.initial_requests(cursor)
        self.crawler.stats.set_value("adapter/entrypoints_total", len(specifications))
        for specification in specifications:
            yield self._request(specification, self.parse_listing)

    def parse_listing(self, response: scrapy.http.Response):
        if not 200 <= response.status < 300:
            self._record_error(f"入口响应失败: {response.status} {response.url}")
            return
        self.crawler.stats.inc_value("adapter/entrypoints_succeeded")
        try:
            payload = self._payload(response)
            listing_requests = self.adapter.listing_requests(payload)
            references = self.adapter.discover(payload)
        except Exception as exc:
            self._record_error(f"入口解析失败: {response.url}: {exc}")
            return
        if listing_requests:
            self.crawler.stats.inc_value("adapter/entrypoints_total", len(listing_requests))
            for specification in listing_requests:
                yield self._request(specification, self.parse_listing)
        for reference in references:
            if reference.url in self._seen_details or len(self._seen_details) >= self.max_details:
                continue
            self._seen_details.add(reference.url)
            self.crawler.stats.inc_value("adapter/detail_discovered")
            specification = self.adapter.detail_request(reference)
            yield self._request(
                specification,
                self.parse_detail,
                cb_kwargs={"reference_data": asdict(reference)},
            )

    def parse_detail(self, response: scrapy.http.Response, reference_data: dict[str, Any]):
        if not 200 <= response.status < 300:
            self._record_error(f"详情响应失败: {response.status} {response.url}")
            return
        self.crawler.stats.inc_value("adapter/detail_fetched")
        reference = DocumentReference(**reference_data)
        try:
            document = self.adapter.parse_document(self._payload(response), reference)
        except Exception as exc:
            self._record_error(f"详情解析失败: {response.url}: {exc}")
            return
        if not document:
            self._record_error(f"详情没有产出合格文档: {response.url}")
            return
        self._documents.append(document)
        self.crawler.stats.inc_value("adapter/documents_emitted")
        for media_url in document.get("metadata", {}).get("media_urls", []):
            self.crawler.stats.inc_value("adapter/media_discovered")
            yield self._request(
                RequestSpec(
                    url=media_url,
                    kind="media",
                    metadata={
                        "source_document_id": document["source_document_id"],
                        "document_type": document["type"],
                    },
                ),
                self.parse_media,
            )
        yield document

    def parse_media(self, response: scrapy.http.Response):
        if not 200 <= response.status < 300:
            self._record_error(f"正文图像响应失败: {response.status} {response.url}")
            return
        content_type = response.headers.get(b"Content-Type", b"")
        if isinstance(content_type, bytes):
            content_type = content_type.decode("latin-1")
        if not str(content_type).lower().startswith("image/"):
            self._record_error(f"正文图像类型异常: {content_type or 'unknown'} {response.url}")
            return
        self.crawler.stats.inc_value("adapter/media_fetched")

    def handle_request_error(self, failure) -> None:
        request = failure.request
        request_kind = request.meta.get("qsou_request_kind", "request")
        message = failure.getErrorMessage()
        self._record_error(f"{request_kind} 请求失败: {request.url}: {message}")

    def closed(self, reason: str) -> None:
        if not self.report_path:
            return
        report = {
            "source_id": self.source_id,
            "adapter_id": self.adapter.adapter_id,
            "adapter_version": self.adapter.version,
            "close_reason": reason,
            "entrypoints_total": self.crawler.stats.get_value("adapter/entrypoints_total", 0),
            "entrypoints_succeeded": self.crawler.stats.get_value("adapter/entrypoints_succeeded", 0),
            "detail_discovered": self.crawler.stats.get_value("adapter/detail_discovered", 0),
            "detail_fetched": self.crawler.stats.get_value("adapter/detail_fetched", 0),
            "documents_emitted": self.crawler.stats.get_value("adapter/documents_emitted", 0),
            "documents_indexed": self.crawler.stats.get_value("adapter/documents_indexed", 0),
            "media_discovered": self.crawler.stats.get_value("adapter/media_discovered", 0),
            "media_fetched": self.crawler.stats.get_value("adapter/media_fetched", 0),
            "evidence_archived": self.crawler.stats.get_value("adapter/evidence_archived", 0),
            "failures": self.crawler.stats.get_value("adapter/failures", 0),
            "download_timeout_seconds": self.crawler.settings.getint("DOWNLOAD_TIMEOUT"),
            "errors": self._errors[-20:],
            "cursor": self.adapter.cursor_candidate(self._documents),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.report_path)

    def _request(self, specification: RequestSpec, callback, cb_kwargs=None):
        metadata = dict(specification.metadata)
        metadata["qsou_request_kind"] = specification.kind
        return scrapy.Request(
            url=specification.url,
            method=specification.method,
            body=specification.body,
            headers=dict(specification.headers),
            callback=callback,
            errback=self.handle_request_error,
            cb_kwargs=cb_kwargs or {},
            meta=metadata,
            dont_filter=specification.kind == "listing",
        )

    @staticmethod
    def _payload(response: scrapy.http.Response) -> ResponsePayload:
        content_type = response.headers.get(b"Content-Type", b"application/octet-stream")
        if isinstance(content_type, bytes):
            content_type = content_type.decode("latin-1")
        return ResponsePayload(
            url=response.url,
            body=response.body,
            status=response.status,
            content_type=str(content_type),
            encoding=getattr(response, "encoding", None),
            metadata=dict(response.meta),
        )

    def _record_error(self, message: str) -> None:
        self._errors.append(message)
        self.crawler.stats.inc_value("adapter/failures")
        self.logger.warning(message)
