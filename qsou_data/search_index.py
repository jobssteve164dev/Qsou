"""Rebuildable Elasticsearch projection of PostgreSQL standard documents."""

from __future__ import annotations

import os
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
        actions = (
            self._action(document, projection_generation=projection_generation)
            for document in documents
        )
        for succeeded, result in helpers.streaming_bulk(
            self.client,
            actions,
            raise_on_error=True,
            refresh=False,
        ):
            if succeeded:
                operation = next(iter(result.values()))
                indexed.append(str(operation["_id"]))
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
        content_version_id = str(document.get("content_version_id") or document.get("id") or "")
        if not content_version_id:
            raise RuntimeError("标准文档缺少 content_version_id")
        content = str(document.get("content") or "")
        source_id = str(document.get("source_id") or "")
        source = {
            "content_version_id": content_version_id,
            "canonical_document_id": document.get("canonical_document_id"),
            "title": str(document.get("title") or ""),
            "content": content,
            "summary": content[:300],
            "source": document.get("source") or source_id,
            "source_id": source_id,
            "url": document.get("url"),
            "published_at": document.get("source_published_at") or document.get("publish_time"),
            "fetched_at": document.get("fetched_at"),
            "tags": list(document.get("tags") or []),
            "raw_object_id": document.get("raw_object_id"),
            "active": bool(document.get("active", True)),
            "title_suggest": str(document.get("title") or ""),
        }
        if projection_generation:
            source["projection_generation"] = projection_generation
        return {
            "_op_type": "index",
            "_index": self.alias,
            "_id": content_version_id,
            "_source": source,
        }
