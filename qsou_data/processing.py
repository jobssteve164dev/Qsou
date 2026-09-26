"""Baseline standard-document processing without external runtime services."""

from __future__ import annotations

import html
import re
from typing import Any, Mapping

from .store import utc_now


PROCESSING_VERSION = "qsou-baseline/1"
_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_SENTENCE_PATTERN = re.compile(r"(?<=[。！？!?])")
_ENTITY_PATTERNS = {
    "stock_code": re.compile(r"(?<!\d)\d{6}(?!\d)"),
    "money": re.compile(r"\d+(?:\.\d+)?(?:万|亿|千|百)?元"),
    "percentage": re.compile(r"\d+(?:\.\d+)?%"),
    "date": re.compile(r"\d{4}年\d{1,2}月\d{1,2}日"),
    "company": re.compile(r"[A-Za-z\u4e00-\u9fff]{2,30}(?:股份有限公司|有限公司|集团)"),
}
_CATEGORY_KEYWORDS = {
    "财务指标": ("营业收入", "营收", "净利润", "利润", "现金流", "资产", "负债"),
    "市场动态": ("股票", "股价", "成交量", "市值", "IPO", "并购", "回购"),
    "监管政策": ("监管", "政策", "法规", "证监会", "交易所", "处罚", "信息披露"),
    "宏观经济": ("GDP", "CPI", "PPI", "PMI", "利率", "汇率", "通胀"),
}
_KEYWORDS = tuple(
    dict.fromkeys(
        keyword
        for keywords in _CATEGORY_KEYWORDS.values()
        for keyword in keywords
    )
)


class BaselineDocumentProcessor:
    """Create deterministic search features from a persisted standard document."""

    def process(self, document: Mapping[str, Any]) -> dict[str, Any]:
        title = str(document.get("title") or "").strip()
        content = str(document.get("content") or "")
        processed_content = self._clean_text(content)
        combined = f"{title}\n{processed_content}"
        keywords = [keyword for keyword in _KEYWORDS if keyword in combined]
        categories = [
            category
            for category, candidates in _CATEGORY_KEYWORDS.items()
            if any(keyword in combined for keyword in candidates)
        ]
        entities = self._entities(combined)
        quality = self._quality(document, title, processed_content)
        return {
            "processing_version": PROCESSING_VERSION,
            "processed_at": utc_now(),
            "processed_content": processed_content,
            "summary": self._summary(processed_content, title),
            "keywords": keywords[:20],
            "categories": categories,
            "entities": entities,
            "quality": quality,
        }

    @staticmethod
    def _clean_text(value: str) -> str:
        without_tags = _TAG_PATTERN.sub(" ", html.unescape(value))
        return _WHITESPACE_PATTERN.sub(" ", without_tags).strip()

    @staticmethod
    def _summary(content: str, title: str) -> str:
        sentences = [
            sentence.strip()
            for sentence in _SENTENCE_PATTERN.split(content)
            if sentence.strip()
        ]
        summary = "".join(sentences[:3]) or title
        return summary[:300]

    @staticmethod
    def _entities(value: str) -> list[dict[str, str]]:
        entities: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for entity_type, pattern in _ENTITY_PATTERNS.items():
            for match in pattern.findall(value):
                key = (entity_type, match)
                if key in seen:
                    continue
                seen.add(key)
                entities.append({"text": match, "type": entity_type})
        return entities

    @staticmethod
    def _quality(
        document: Mapping[str, Any],
        title: str,
        content: str,
    ) -> dict[str, Any]:
        checks = {
            "title": bool(title),
            "content": len(content) >= 50,
            "url": bool(document.get("url")),
            "source": bool(document.get("source_id") or document.get("source")),
            "evidence": bool(document.get("raw_object_id")),
        }
        score = round(sum(checks.values()) / len(checks), 3)
        return {
            "score": score,
            "accepted": score >= 0.6,
            "checks": checks,
        }


def run_processing_batch(store, processor, *, batch_size: int) -> dict[str, int]:
    documents = store.claim_processing_documents(batch_size)
    processed = 0
    filtered = 0
    failed = 0
    for document in documents:
        content_version_id = str(
            document.get("content_version_id") or document.get("id") or ""
        )
        try:
            processing = processor.process(document)
            accepted = bool((processing.get("quality") or {}).get("accepted", True))
            if accepted:
                saved = store.save_processing_result(content_version_id, processing)
                if saved is False:
                    filtered += 1
                else:
                    processed += 1
            else:
                store.save_processing_result(
                    content_version_id,
                    processing,
                    state="filtered",
                )
                filtered += 1
        except Exception as exc:
            store.mark_failed(
                [content_version_id],
                f"processing: {exc}"[:1000],
            )
            failed += 1
    return {
        "claimed": len(documents),
        "processed": processed,
        "filtered": filtered,
        "processing_failed": failed,
    }
