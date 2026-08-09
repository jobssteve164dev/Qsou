"""Rebuildable Elasticsearch projection of PostgreSQL standard documents."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

from elasticsearch import Elasticsearch, helpers


INDEX_MAPPINGS = {
    "properties": {
        "content_version_id": {"type": "keyword"},
        "canonical_document_id": {"type": "keyword"},
        "title": {"type": "text", "analyzer": "standard"},
        "content": {"type": "text", "analyzer": "standard"},
        "summary": {"type": "text", "analyzer": "standard"},
        "source": {"type": "keyword"},
        "source_id": {"type": "keyword"},
        "url": {"type": "keyword"},
        "published_at": {"type": "date"},
        "fetched_at": {"type": "date"},
        "tags": {"type": "keyword"},
        "raw_object_id": {"type": "keyword"},
        "active": {"type": "boolean"},
        "projection_generation": {"type": "keyword"},
        "title_suggest": {"type": "completion", "analyzer": "standard"},
    }
}
INDEX_SETTINGS = {"number_of_shards": 1, "number_of_replicas": 0}


def normalize_index_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", " ")


def normalize_index_date(value: Any) -> str | int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = normalize_index_text(value).strip()
    if not text:
        return None
    if re.fullmatch(r"[0-9]{8}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", text):
        return datetime.strptime(text, "%Y%m%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        ).isoformat()

    candidate = text.replace(" ", "T", 1)
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00")).isoformat()
    except ValueError:
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return None


class ElasticsearchIndex:
    def __init__(self) -> None:
        self.url = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200").strip()
        self.alias = os.getenv("ELASTICSEARCH_INDEX_ALIAS", "qsou_documents").strip()
        if not self.url or not self.alias:
            raise RuntimeError("Elasticsearch 索引器缺少连接地址或索引别名")
        self.client = Elasticsearch(
            self.url,
            request_timeout=15,
            max_retries=3,
            retry_on_timeout=True,
        )

    def ensure_ready(self) -> None:
        if not self.client.ping():
            raise RuntimeError("Elasticsearch 不可用")
        if self.client.indices.exists_alias(name=self.alias):
            self.client.indices.put_mapping(index=self.alias, properties=INDEX_MAPPINGS["properties"])
            return
        if self.client.indices.exists(index=self.alias):
            self.client.indices.put_mapping(index=self.alias, properties=INDEX_MAPPINGS["properties"])
            return
        target = f"{self.alias}_v1"
        if not self.client.indices.exists(index=target):
            self.client.indices.create(
                index=target,
                mappings=INDEX_MAPPINGS,
                settings=INDEX_SETTINGS,
            )
        self.client.indices.put_alias(index=target, name=self.alias)

    def index_documents(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        projection_generation: str | None = None,
    ) -> list[str]:
        indexed: list[str] = []
        failures: list[dict[str, Any]] = []
        actions = (
            self._action(document, projection_generation=projection_generation)
            for document in documents
        )
        for succeeded, result in helpers.streaming_bulk(
            self.client,
            actions,
            raise_on_error=False,
            refresh=False,
        ):
            operation = next(iter(result.values()))
            if succeeded:
                indexed.append(str(operation["_id"]))
                continue
            failures.append(
                {
                    "id": str(operation.get("_id") or ""),
                    "status": operation.get("status"),
                    "error": operation.get("error"),
                }
            )
        if failures:
            raise RuntimeError(
                f"Elasticsearch 拒绝 {len(failures)} 个文档: "
                + json.dumps(failures[:5], ensure_ascii=False, default=str)
            )
        return indexed

    def delete_stale(self, projection_generation: str) -> int:
        response = self.client.delete_by_query(
            index=self.alias,
            query={
                "bool": {
                    "must_not": {
                        "term": {"projection_generation": projection_generation}
                    }
                }
            },
            conflicts="proceed",
            refresh=False,
        )
        return int(response.get("deleted", 0))

    def refresh(self) -> None:
        self.client.indices.refresh(index=self.alias)

    def active_document_count(self) -> int:
        response = self.client.count(
            index=self.alias,
            query={"term": {"active": True}},
        )
        return int(response["count"])

    def close(self) -> None:
        self.client.close()

    def _action(
        self,
        document: Mapping[str, Any],
        *,
        projection_generation: str | None = None,
    ) -> dict[str, Any]:
        content_version_id = normalize_index_text(
            document.get("content_version_id") or document.get("id")
        )
        if not content_version_id:
            raise RuntimeError("标准文档缺少 content_version_id")
        content = normalize_index_text(document.get("content"))
        source_id = normalize_index_text(document.get("source_id"))
        raw_tags = document.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        source = {
            "content_version_id": content_version_id,
            "canonical_document_id": normalize_index_text(
                document.get("canonical_document_id")
            )
            or None,
            "title": normalize_index_text(document.get("title")),
            "content": content,
            "summary": content[:300],
            "source": normalize_index_text(document.get("source") or source_id),
            "source_id": source_id,
            "url": normalize_index_text(document.get("url")) or None,
            "published_at": normalize_index_date(
                document.get("source_published_at") or document.get("publish_time")
            ),
            "fetched_at": normalize_index_date(document.get("fetched_at")),
            "tags": [
                normalized
                for tag in raw_tags
                if (normalized := normalize_index_text(tag).strip())
            ],
            "raw_object_id": normalize_index_text(document.get("raw_object_id")) or None,
            "active": bool(document.get("active", True)),
        }
        if source["title"]:
            source["title_suggest"] = source["title"]
        if projection_generation:
            source["projection_generation"] = projection_generation
        return {
            "_op_type": "index",
            "_index": self.alias,
            "_id": content_version_id,
            "_source": source,
        }
