"""原始证据、标准文档与可靠处理队列。"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .registry import SourceRegistry, project_root


PROCESSING_VERSION = "qsou-data-baseline/1"
SAFE_RESPONSE_HEADERS = {
    "content-type",
    "content-language",
    "content-length",
    "etag",
    "last-modified",
    "cache-control",
}
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"spm", "from", "source", "ref", "referrer"}


class DataAssetError(RuntimeError):
    """数据资产约束未满足。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_data_root() -> Path:
    configured = os.getenv("QSOU_DATA_ROOT")
    return Path(configured).expanduser().resolve() if configured else project_root() / "data" / "qsou"


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_QUERY_KEYS or any(lowered.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query.append((key, value))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))


def stable_hash(*parts: Any) -> str:
    digest = hashlib.sha256()
    for part in parts:
        value = part if isinstance(part, bytes) else str(part).encode("utf-8")
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class DataAssetStore:
    """以文件归档和 SQLite 目录构成最小可部署事实权威。"""

    def __init__(
        self,
        root: Optional[Path] = None,
        registry: Optional[SourceRegistry] = None,
    ) -> None:
        self.root = Path(root or default_data_root()).resolve()
        self.registry = registry or SourceRegistry()
        self.objects_dir = self.root / "objects"
        self.catalog_path = self.root / "catalog.sqlite3"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_catalog()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.catalog_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_catalog(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS raw_objects (
                    raw_object_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    body_path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    encoding TEXT,
                    response_headers_json TEXT NOT NULL,
                    collector TEXT NOT NULL,
                    first_fetched_at TEXT NOT NULL,
                    last_fetched_at TEXT NOT NULL,
                    fetch_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_raw_source_time
                    ON raw_objects(source_id, first_fetched_at DESC);

                CREATE TABLE IF NOT EXISTS standard_documents (
                    content_version_id TEXT PRIMARY KEY,
                    canonical_document_id TEXT NOT NULL,
                    source_document_id TEXT NOT NULL,
                    raw_object_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_published_at TEXT,
                    first_seen_at TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    processed_at TEXT,
                    indexed_at TEXT,
                    superseded_at TEXT,
                    parser_version TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(raw_object_id) REFERENCES raw_objects(raw_object_id)
                );
                CREATE INDEX IF NOT EXISTS idx_docs_canonical
                    ON standard_documents(canonical_document_id, first_seen_at);
                CREATE INDEX IF NOT EXISTS idx_docs_source_time
                    ON standard_documents(source_id, first_seen_at DESC);

                CREATE TABLE IF NOT EXISTS document_evidence (
                    content_version_id TEXT NOT NULL,
                    raw_object_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY(content_version_id, raw_object_id),
                    FOREIGN KEY(content_version_id) REFERENCES standard_documents(content_version_id),
                    FOREIGN KEY(raw_object_id) REFERENCES raw_objects(raw_object_id)
                );
                INSERT OR IGNORE INTO document_evidence (
                    content_version_id, raw_object_id, observed_at
                )
                SELECT content_version_id, raw_object_id, fetched_at FROM standard_documents;

                CREATE TABLE IF NOT EXISTS processing_outbox (
                    content_version_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    task_id TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(content_version_id) REFERENCES standard_documents(content_version_id)
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_state
                    ON processing_outbox(state, updated_at);
                """
            )

    def health(self) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return {
            "status": "healthy",
            "data_root": str(self.root),
            "catalog": str(self.catalog_path),
        }

    def archive_response(
        self,
        *,
        source_id: str,
        url: str,
        status_code: int,
        response_headers: Optional[Mapping[Any, Any]],
        body: bytes,
        fetched_at: Optional[str] = None,
        content_type: str = "application/octet-stream",
        encoding: Optional[str] = None,
        collector: str = "qsou-crawler",
    ) -> Dict[str, Any]:
        self.registry.get(source_id)
        if not isinstance(body, bytes):
            raise DataAssetError("原始证据正文必须是 bytes")

        canonical_url = canonicalize_url(url)
        content_hash = hashlib.sha256(body).hexdigest()
        raw_object_id = stable_hash(source_id, canonical_url, content_hash)
        fetched_at = fetched_at or utc_now()
        relative_body_path = Path("objects") / raw_object_id[:2] / f"{raw_object_id}.body"
        body_path = self.root / relative_body_path
        self._write_once(body_path, body)

        safe_headers = self._safe_headers(response_headers or {})
        metadata = {
            "raw_object_id": raw_object_id,
            "source_id": source_id,
            "url": canonical_url,
            "status_code": int(status_code),
            "content_hash": content_hash,
            "body_path": relative_body_path.as_posix(),
            "content_type": content_type or "application/octet-stream",
            "encoding": encoding,
            "response_headers": safe_headers,
            "collector": collector,
            "fetched_at": fetched_at,
        }
        metadata_path = body_path.with_suffix(".json")
        self._write_once(metadata_path, json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"))

        with self._connection() as connection:
            existing = connection.execute(
                "SELECT raw_object_id FROM raw_objects WHERE raw_object_id = ?",
                (raw_object_id,),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE raw_objects
                    SET last_fetched_at = ?, fetch_count = fetch_count + 1
                    WHERE raw_object_id = ?
                    """,
                    (fetched_at, raw_object_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO raw_objects (
                        raw_object_id, source_id, url, status_code, content_hash,
                        body_path, content_type, encoding, response_headers_json,
                        collector, first_fetched_at, last_fetched_at, fetch_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        raw_object_id,
                        source_id,
                        canonical_url,
                        int(status_code),
                        content_hash,
                        relative_body_path.as_posix(),
                        content_type or "application/octet-stream",
                        encoding,
                        _json(safe_headers),
                        collector,
                        fetched_at,
                        fetched_at,
                        utc_now(),
                    ),
                )

        return self.get_evidence(raw_object_id)

    def register_document(self, raw_document: Mapping[str, Any]) -> Dict[str, Any]:
        document = dict(raw_document)
        metadata = dict(document.get("metadata") or {})
        url = canonicalize_url(str(document.get("url") or metadata.get("final_url") or ""))
        if not url:
            raise DataAssetError("标准文档缺少 url")

        source_id = str(document.get("source_id") or metadata.get("source_id") or "")
        if not source_id:
            source_id = self.registry.resolve_url(url)["source_id"]
        self.registry.get(source_id)

        raw_object_id = str(document.get("raw_object_id") or metadata.get("raw_object_id") or "")
        if not raw_object_id:
            raise DataAssetError("标准文档必须关联 raw_object_id")
        if not self._raw_exists(raw_object_id):
            raise DataAssetError(f"原始证据不存在: {raw_object_id}")

        title = str(document.get("title") or "").strip()
        content = str(document.get("content") or "").strip()
        if not title or not content:
            raise DataAssetError("标准文档必须包含 title 和 content")

        source_document_id = str(
            document.get("source_document_id")
            or document.get("announcement_id")
            or document.get("id")
            or stable_hash(url)
        )
        canonical_document_id = stable_hash(source_id, source_document_id)
        content_hash = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()
        content_version_id = stable_hash(canonical_document_id, content_hash)
        existing_state = self._document_state(content_version_id)
        fetched_at = str(document.get("fetched_at") or metadata.get("fetched_at") or utc_now())
        parser_version = str(document.get("parser_version") or metadata.get("parser_version") or PROCESSING_VERSION)
        document_type = str(document.get("type") or document.get("category") or "document")
        source_published_at = (
            document.get("source_published_at")
            or document.get("publish_time")
            or document.get("published_at")
            or existing_state.get("source_published_at")
        )
        processed_at = document.get("processed_at") or existing_state.get("processed_at")
        indexed_at = document.get("indexed_at") or existing_state.get("indexed_at")

        with self._connection() as connection:
            first_row = connection.execute(
                """
                SELECT MIN(first_seen_at) AS first_seen_at
                FROM standard_documents WHERE canonical_document_id = ?
                """,
                (canonical_document_id,),
            ).fetchone()
            first_seen_at = first_row["first_seen_at"] if first_row and first_row["first_seen_at"] else fetched_at

            standard_document = dict(document)
            standard_document.update(
                {
                    "id": content_version_id,
                    "source_id": source_id,
                    "source_document_id": source_document_id,
                    "canonical_document_id": canonical_document_id,
                    "content_version_id": content_version_id,
                    "raw_object_id": raw_object_id,
                    "content_hash": content_hash,
                    "url": url,
                    "source_published_at": source_published_at,
                    "first_seen_at": first_seen_at,
                    "fetched_at": fetched_at,
                    "processed_at": processed_at,
                    "indexed_at": indexed_at,
                    "parser_version": parser_version,
                }
            )
            metadata.update(
                {
                    "source_id": source_id,
                    "raw_object_id": raw_object_id,
                    "fetched_at": fetched_at,
                    "parser_version": parser_version,
                }
            )
            standard_document["metadata"] = metadata

            now = utc_now()
            connection.execute(
                """
                UPDATE standard_documents
                SET active = 0, superseded_at = COALESCE(superseded_at, ?)
                WHERE canonical_document_id = ? AND content_version_id <> ? AND active = 1
                """,
                (now, canonical_document_id, content_version_id),
            )
            connection.execute(
                """
                INSERT INTO standard_documents (
                    content_version_id, canonical_document_id, source_document_id,
                    raw_object_id, source_id, document_type, title, content, url,
                    content_hash, source_published_at, first_seen_at, fetched_at,
                    processed_at, indexed_at, superseded_at, parser_version,
                    document_json, active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 1, ?)
                ON CONFLICT(content_version_id) DO UPDATE SET
                    raw_object_id = excluded.raw_object_id,
                    source_published_at = excluded.source_published_at,
                    fetched_at = excluded.fetched_at,
                    parser_version = excluded.parser_version,
                    document_json = excluded.document_json,
                    active = 1,
                    superseded_at = NULL
                """,
                (
                    content_version_id,
                    canonical_document_id,
                    source_document_id,
                    raw_object_id,
                    source_id,
                    document_type,
                    title,
                    content,
                    url,
                    content_hash,
                    source_published_at,
                    first_seen_at,
                    fetched_at,
                    processed_at,
                    indexed_at,
                    parser_version,
                    _json(standard_document),
                    now,
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO document_evidence (
                    content_version_id, raw_object_id, observed_at
                ) VALUES (?, ?, ?)
                """,
                (content_version_id, raw_object_id, fetched_at),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO processing_outbox (
                    content_version_id, state, attempts, task_id, last_error, updated_at
                ) VALUES (?, 'pending', 0, NULL, NULL, ?)
                """,
                (content_version_id, now),
            )

        return self.get_document(content_version_id)

    def pending_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 1000))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT d.document_json, o.state, o.attempts
                FROM processing_outbox o
                JOIN standard_documents d USING(content_version_id)
                WHERE o.state IN ('pending', 'failed')
                ORDER BY o.updated_at ASC
                LIMIT ?
                """,
                (bounded,),
            ).fetchall()
        return [json.loads(row["document_json"]) for row in rows]

    def mark_dispatched(self, content_version_ids: Sequence[str], task_id: str) -> None:
        self._set_outbox_state(content_version_ids, "dispatched", task_id=task_id)

    def mark_processing(self, content_version_ids: Sequence[str]) -> None:
        self._set_outbox_state(content_version_ids, "processing")

    def mark_processed(self, content_version_ids: Sequence[str]) -> None:
        now = utc_now()
        self._set_outbox_state(content_version_ids, "processed")
        self._update_document_timestamp(content_version_ids, "processed_at", now)

    def mark_filtered(self, content_version_ids: Sequence[str], reason: str) -> None:
        self._set_outbox_state(content_version_ids, "filtered", error=reason)

    def mark_indexed(self, content_version_ids: Sequence[str]) -> None:
        now = utc_now()
        self._set_outbox_state(content_version_ids, "indexed")
        self._update_document_timestamp(content_version_ids, "indexed_at", now)

    def mark_failed(self, content_version_ids: Sequence[str], error: str) -> None:
        self._set_outbox_state(content_version_ids, "failed", error=error)

    def requeue(self, source_id: Optional[str] = None, limit: int = 1000) -> int:
        bounded = max(1, min(int(limit), 10000))
        parameters: List[Any] = []
        where = ""
        if source_id:
            self.registry.get(source_id)
            where = "WHERE d.source_id = ?"
            parameters.append(source_id)
        parameters.append(bounded)

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT d.content_version_id
                FROM standard_documents d
                {where}
                ORDER BY d.first_seen_at ASC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
            ids = [row["content_version_id"] for row in rows]
            now = utc_now()
            connection.executemany(
                """
                INSERT INTO processing_outbox (
                    content_version_id, state, attempts, task_id, last_error, updated_at
                ) VALUES (?, 'pending', 0, NULL, NULL, ?)
                ON CONFLICT(content_version_id) DO UPDATE SET
                    state = 'pending', task_id = NULL, last_error = NULL, updated_at = excluded.updated_at
                """,
                [(content_version_id, now) for content_version_id in ids],
            )
        return len(ids)

    def status(self) -> Dict[str, Any]:
        with self._connection() as connection:
            raw_count = connection.execute("SELECT COUNT(*) AS count FROM raw_objects").fetchone()["count"]
            document_count = connection.execute("SELECT COUNT(*) AS count FROM standard_documents").fetchone()["count"]
            active_count = connection.execute(
                "SELECT COUNT(*) AS count FROM standard_documents WHERE active = 1"
            ).fetchone()["count"]
            outbox_rows = connection.execute(
                "SELECT state, COUNT(*) AS count FROM processing_outbox GROUP BY state"
            ).fetchall()

        collector = {"state": "not_started"}
        collector_status_path = self.root / "collector-status.json"
        if collector_status_path.is_file():
            try:
                loaded = json.loads(collector_status_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    collector = loaded
            except (OSError, json.JSONDecodeError):
                collector = {"state": "unknown"}

        return {
            "status": "healthy",
            "registered_sources": len(self.registry.all(enabled_only=True)),
            "raw_objects": raw_count,
            "document_versions": document_count,
            "active_documents": active_count,
            "processing": {row["state"]: row["count"] for row in outbox_rows},
            "collector": collector,
        }

    def list_sources(self) -> List[Dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT source_id, COUNT(*) AS raw_count,
                       MAX(last_fetched_at) AS last_fetched_at
                FROM raw_objects GROUP BY source_id
                """
            ).fetchall()
        observed = {row["source_id"]: dict(row) for row in rows}

        result = []
        for source in self.registry.all():
            metrics = observed.get(source["source_id"], {})
            entry = dict(source)
            entry["raw_count"] = metrics.get("raw_count", 0)
            entry["last_fetched_at"] = metrics.get("last_fetched_at")
            entry["health_state"] = (
                "collecting" if metrics.get("last_fetched_at") else source.get("health_state", "configured")
            )
            result.append(entry)
        return result

    def list_evidence(
        self,
        source_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        parameters: List[Any] = []
        where = ""
        if source_id:
            self.registry.get(source_id)
            where = "WHERE source_id = ?"
            parameters.append(source_id)
        parameters.extend([bounded, offset])

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM raw_objects {where}
                ORDER BY first_fetched_at DESC LIMIT ? OFFSET ?
                """,
                parameters,
            ).fetchall()
        return [self._evidence_row(row) for row in rows]

    def get_evidence(self, raw_object_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM raw_objects WHERE raw_object_id = ?",
                (raw_object_id,),
            ).fetchone()
        if not row:
            raise KeyError(raw_object_id)
        return self._evidence_row(row)

    def evidence_body_path(self, raw_object_id: str) -> Path:
        evidence = self.get_evidence(raw_object_id)
        path = (self.root / evidence["body_path"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise DataAssetError(f"原始证据文件不可用: {raw_object_id}")
        return path

    def evidence_has_document(self, raw_object_id: str) -> bool:
        """Return whether one immutable response is already linked to a document."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM document_evidence WHERE raw_object_id = ? LIMIT 1",
                (raw_object_id,),
            ).fetchone()
        return row is not None

    def get_document(self, content_version_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT document_json FROM standard_documents WHERE content_version_id = ?",
                (content_version_id,),
            ).fetchone()
            evidence_rows = connection.execute(
                """
                SELECT raw_object_id FROM document_evidence
                WHERE content_version_id = ? ORDER BY observed_at ASC
                """,
                (content_version_id,),
            ).fetchall()
        if not row:
            raise KeyError(content_version_id)
        document = json.loads(row["document_json"])
        document["raw_object_ids"] = [item["raw_object_id"] for item in evidence_rows]
        return document

    def search_documents(
        self,
        query: str,
        *,
        source_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query = query.strip()
        if not query:
            return {"total_count": 0, "results": []}
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))
        terms = [term.lower() for term in query.split() if term] or [query.lower()]
        clauses = []
        parameters: List[Any] = []
        for term in terms:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)")
            wildcard = f"%{term}%"
            parameters.extend([wildcard, wildcard])
        where = "active = 1 AND " + " AND ".join(clauses)
        if source_id:
            self.registry.get(source_id)
            where += " AND source_id = ?"
            parameters.append(source_id)

        with self._connection() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) AS count FROM standard_documents WHERE {where}",
                parameters,
            ).fetchone()["count"]
            rows = connection.execute(
                f"""
                SELECT content_version_id, title, content, source_id, url,
                       source_published_at, fetched_at, document_json
                FROM standard_documents
                WHERE {where}
                ORDER BY COALESCE(source_published_at, fetched_at) DESC
                LIMIT ? OFFSET ?
                """,
                parameters + [page_size, (page - 1) * page_size],
            ).fetchall()

        results = []
        for row in rows:
            document = json.loads(row["document_json"])
            haystack = f"{row['title']} {row['content']}".lower()
            matched = sum(haystack.count(term) for term in terms)
            score = min(1.0, 0.5 + 0.1 * matched)
            results.append(
                {
                    "id": row["content_version_id"],
                    "title": row["title"],
                    "content": row["content"][:500],
                    "source": document.get("source") or row["source_id"],
                    "source_id": row["source_id"],
                    "url": row["url"],
                    "published_at": row["source_published_at"] or row["fetched_at"],
                    "relevance_score": score,
                    "tags": document.get("tags", []),
                    "raw_object_id": document.get("raw_object_id"),
                }
            )
        return {"total_count": total, "results": results}

    def export_documents(self, source_id: Optional[str] = None) -> Iterable[Dict[str, Any]]:
        parameters: List[Any] = []
        where = ""
        if source_id:
            self.registry.get(source_id)
            where = "WHERE source_id = ?"
            parameters.append(source_id)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT content_version_id FROM standard_documents {where} ORDER BY first_seen_at ASC",
                parameters,
            ).fetchall()
        for row in rows:
            yield self.get_document(row["content_version_id"])

    def _document_state(self, content_version_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT source_published_at, processed_at, indexed_at
                FROM standard_documents WHERE content_version_id = ?
                """,
                (content_version_id,),
            ).fetchone()
        return dict(row) if row else {}

    def _update_document_timestamp(
        self,
        content_version_ids: Sequence[str],
        field: str,
        value: str,
    ) -> None:
        if field not in {"processed_at", "indexed_at"}:
            raise ValueError(f"不支持的文档时间字段: {field}")
        ids = [content_version_id for content_version_id in content_version_ids if content_version_id]
        if not ids:
            return
        with self._connection() as connection:
            for content_version_id in ids:
                row = connection.execute(
                    "SELECT document_json FROM standard_documents WHERE content_version_id = ?",
                    (content_version_id,),
                ).fetchone()
                if not row:
                    continue
                document = json.loads(row["document_json"])
                document[field] = value
                connection.execute(
                    f"""
                    UPDATE standard_documents
                    SET {field} = ?, document_json = ?
                    WHERE content_version_id = ?
                    """,
                    (value, _json(document), content_version_id),
                )

    def _raw_exists(self, raw_object_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM raw_objects WHERE raw_object_id = ?",
                (raw_object_id,),
            ).fetchone()
        return bool(row)

    def _set_outbox_state(
        self,
        content_version_ids: Sequence[str],
        state: str,
        *,
        task_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        ids = [value for value in content_version_ids if value]
        if not ids:
            return
        now = utc_now()
        attempt_delta = 1 if state in {"dispatched", "failed"} else 0
        with self._connection() as connection:
            connection.executemany(
                """
                UPDATE processing_outbox
                SET state = ?, attempts = attempts + ?, task_id = COALESCE(?, task_id),
                    last_error = ?, updated_at = ?
                WHERE content_version_id = ?
                """,
                [
                    (state, attempt_delta, task_id, error, now, content_version_id)
                    for content_version_id in ids
                ],
            )

    @staticmethod
    def _safe_headers(headers: Mapping[Any, Any]) -> Dict[str, str]:
        safe: Dict[str, str] = {}
        for raw_key, raw_value in headers.items():
            key = raw_key.decode("latin-1") if isinstance(raw_key, bytes) else str(raw_key)
            normalized = key.lower()
            if normalized not in SAFE_RESPONSE_HEADERS:
                continue
            if isinstance(raw_value, (list, tuple)):
                values = [value.decode("latin-1") if isinstance(value, bytes) else str(value) for value in raw_value]
                value = ", ".join(values)
            else:
                value = raw_value.decode("latin-1") if isinstance(raw_value, bytes) else str(raw_value)
            safe[normalized] = value
        return safe

    def _evidence_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["response_headers"] = json.loads(value.pop("response_headers_json"))
        return value

    @staticmethod
    def _write_once(path: Path, payload: bytes) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(str(temporary_path), str(path))
            except FileExistsError:
                pass
            finally:
                temporary_path.unlink(missing_ok=True)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
