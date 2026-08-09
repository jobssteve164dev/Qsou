"""原始证据、标准文档与可靠处理队列。"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .catalog import Catalog, normalize_catalog_value
from .objects import ObjectStorageError, configured_object_store
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


def schedule_seconds(value: Any) -> int:
    text = str(value or "30m").strip().lower()
    try:
        if text.endswith("m"):
            return max(300, int(text[:-1]) * 60)
        if text.endswith("h"):
            return max(300, int(text[:-1]) * 3600)
        return max(300, int(text))
    except ValueError:
        return 1800


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
    """以不可变对象归档和关系目录库构成数据事实权威。"""

    def __init__(
        self,
        root: Optional[Path] = None,
        registry: Optional[SourceRegistry] = None,
    ) -> None:
        self.root = Path(root or default_data_root()).resolve()
        self.registry = registry or SourceRegistry()
        self.catalog = Catalog(self.root)
        self.object_store = configured_object_store(self.root)
        self.objects_dir = self.root / "objects"
        self.object_cache_dir = self.root / "object-cache"
        self.root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        with self.catalog.connection() as connection:
            yield connection

    def health(self) -> Dict[str, Any]:
        with self._connection() as connection:
            connection.execute("SELECT 1").fetchone()
        from .migration_state import migration_state

        migrations = migration_state(self)
        object_storage = self.object_store.health()
        return {
            "status": "healthy" if migrations["status"] == "ready" else "unavailable",
            "data_root": str(self.root),
            "catalog_backend": self.catalog.backend,
            "catalog": self.catalog.label,
            "object_storage": object_storage,
            "migrations": migrations,
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
        source_id = normalize_catalog_value(str(source_id))
        url = normalize_catalog_value(str(url))
        content_type = normalize_catalog_value(
            str(content_type or "application/octet-stream")
        )
        encoding = normalize_catalog_value(encoding) if encoding is not None else None
        collector = normalize_catalog_value(str(collector))
        fetched_at = normalize_catalog_value(fetched_at) if fetched_at is not None else None
        self.registry.get(source_id)
        if not isinstance(body, bytes):
            raise DataAssetError("原始证据正文必须是 bytes")

        canonical_url = canonicalize_url(url)
        content_hash = hashlib.sha256(body).hexdigest()
        raw_object_id = stable_hash(source_id, canonical_url, content_hash)
        fetched_at = fetched_at or utc_now()
        relative_body_path = Path("objects") / raw_object_id[:2] / f"{raw_object_id}.body"
        body_key = relative_body_path.as_posix()
        try:
            self.object_store.put_once(body_key, body, content_type or "application/octet-stream")
        except ObjectStorageError as exc:
            raise DataAssetError(str(exc)) from exc

        safe_headers = self._safe_headers(response_headers or {})
        metadata = {
            "raw_object_id": raw_object_id,
            "source_id": source_id,
            "url": canonical_url,
            "status_code": int(status_code),
            "content_hash": content_hash,
            "body_path": body_key,
            "content_type": content_type or "application/octet-stream",
            "encoding": encoding,
            "response_headers": safe_headers,
            "collector": collector,
            "fetched_at": fetched_at,
        }
        metadata_key = str(Path(body_key).with_suffix(".json"))
        try:
            self.object_store.put_once(
                metadata_key,
                json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
                verify_existing=False,
            )
        except ObjectStorageError as exc:
            raise DataAssetError(str(exc)) from exc

        with self._connection() as connection:
            existing = connection.execute(
                "SELECT raw_object_id FROM raw_objects WHERE raw_object_id = %s",
                (raw_object_id,),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE raw_objects
                    SET last_fetched_at = %s, fetch_count = fetch_count + 1
                    WHERE raw_object_id = %s
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
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                    """,
                    (
                        raw_object_id,
                        source_id,
                        canonical_url,
                        int(status_code),
                        content_hash,
                        body_key,
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
        document = dict(normalize_catalog_value(dict(raw_document)))
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
                FROM standard_documents WHERE canonical_document_id = %s
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
                SET active = 0, superseded_at = COALESCE(superseded_at, %s),
                    indexed_at = NULL
                WHERE canonical_document_id = %s AND content_version_id <> %s AND active = 1
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, 1, %s)
                ON CONFLICT(content_version_id) DO UPDATE SET
                    raw_object_id = excluded.raw_object_id,
                    source_published_at = excluded.source_published_at,
                    fetched_at = excluded.fetched_at,
                    parser_version = excluded.parser_version,
                    document_json = excluded.document_json,
                    active = 1,
                    superseded_at = NULL,
                    indexed_at = NULL
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
                INSERT INTO document_evidence (
                    content_version_id, raw_object_id, observed_at
                ) VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (content_version_id, raw_object_id, fetched_at),
            )
            connection.execute(
                """
                INSERT INTO processing_outbox (
                    content_version_id, state, attempts, task_id, last_error, updated_at
                ) VALUES (%s, 'pending', 0, NULL, NULL, %s)
                ON CONFLICT DO NOTHING
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
                WHERE d.active = 1 AND o.state IN ('pending', 'failed', 'processed')
                ORDER BY o.updated_at ASC
                LIMIT %s
                """,
                (bounded,),
            ).fetchall()
        return [json.loads(row["document_json"]) for row in rows]

    def documents_for_index(self) -> Iterable[Dict[str, Any]]:
        """Yield every document version with its current visibility state."""
        with self._connection() as connection:
            cursor = connection.execute(
                """
                SELECT document_json, active FROM standard_documents
                ORDER BY first_seen_at ASC
                """
            )
            while True:
                rows = cursor.fetchmany(500)
                if not rows:
                    break
                for row in rows:
                    document = json.loads(row["document_json"])
                    document["active"] = bool(row["active"])
                    yield document

    def pending_documents_for_index(self, limit: int = 100) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 1000))
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT document_json, active FROM standard_documents
                WHERE indexed_at IS NULL
                ORDER BY first_seen_at ASC
                LIMIT %s
                """,
                (bounded,),
            ).fetchall()
        documents = []
        for row in rows:
            document = json.loads(row["document_json"])
            document["active"] = bool(row["active"])
            documents.append(document)
        return documents

    def active_document_count(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM standard_documents WHERE active = 1"
            ).fetchone()
        return int(row["count"])

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
            where = "WHERE d.source_id = %s"
            parameters.append(source_id)
        parameters.append(bounded)

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT d.content_version_id
                FROM standard_documents d
                {where}
                ORDER BY d.first_seen_at ASC
                LIMIT %s
                """,
                parameters,
            ).fetchall()
            ids = [row["content_version_id"] for row in rows]
            now = utc_now()
            connection.executemany(
                """
                INSERT INTO processing_outbox (
                    content_version_id, state, attempts, task_id, last_error, updated_at
                ) VALUES (%s, 'pending', 0, NULL, NULL, %s)
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

        sources = self.list_sources()
        network_states: Dict[str, int] = {}
        for source in sources:
            state = str(source.get("collection_state") or "not_started")
            network_states[state] = network_states.get(state, 0) + 1

        return {
            "status": "healthy",
            "registered_sources": len(self.registry.all()),
            "active_sources": len(self.registry.all(enabled_only=True)),
            "raw_objects": raw_count,
            "document_versions": document_count,
            "active_documents": active_count,
            "processing": {row["state"]: row["count"] for row in outbox_rows},
            "collector": collector,
            "network": network_states,
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
            document_rows = connection.execute(
                """
                SELECT source_id,
                       COUNT(*) AS document_versions,
                       SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active_documents,
                       MAX(fetched_at) AS last_document_at
                FROM standard_documents GROUP BY source_id
                """
            ).fetchall()
        observed = {row["source_id"]: dict(row) for row in rows}
        documents = {row["source_id"]: dict(row) for row in document_rows}

        result = []
        for source in self.registry.all():
            metrics = observed.get(source["source_id"], {})
            document_metrics = documents.get(source["source_id"], {})
            latest_run = self.latest_adapter_run(source["source_id"])
            active_request = self.active_adapter_run_request(source["source_id"])
            entry = dict(source)
            entry["raw_count"] = metrics.get("raw_count", 0)
            entry["last_fetched_at"] = metrics.get("last_fetched_at")
            entry["document_versions"] = document_metrics.get("document_versions", 0)
            entry["active_documents"] = document_metrics.get("active_documents", 0)
            entry["last_document_at"] = document_metrics.get("last_document_at")
            if not source.get("enabled"):
                entry["collection_state"] = str(source.get("health_state") or "disabled")
            elif active_request:
                entry["collection_state"] = active_request["state"]
            else:
                entry["collection_state"] = latest_run.get("state", "not_started") if latest_run else "not_started"
                if entry["collection_state"] == "healthy" and latest_run.get("finished_at"):
                    try:
                        finished_at = datetime.fromisoformat(
                            str(latest_run["finished_at"]).replace("Z", "+00:00")
                        )
                        stale_after = schedule_seconds(source.get("schedule")) * 2
                        if (datetime.now(timezone.utc) - finished_at).total_seconds() > stale_after:
                            entry["collection_state"] = "stale"
                    except (TypeError, ValueError):
                        entry["collection_state"] = "stale"
            entry["last_run"] = latest_run
            entry["active_request"] = active_request
            entry["cursor"] = self.get_source_cursor(source["source_id"])
            result.append(entry)
        return result

    def source_counts(self, source_id: str) -> Dict[str, int]:
        """Return monotonic source totals used to close one adapter run."""
        self.registry.get(source_id)
        with self._connection() as connection:
            raw_count = connection.execute(
                "SELECT COUNT(*) AS count FROM raw_objects WHERE source_id = %s",
                (source_id,),
            ).fetchone()["count"]
            document_count = connection.execute(
                "SELECT COUNT(*) AS count FROM standard_documents WHERE source_id = %s",
                (source_id,),
            ).fetchone()["count"]
        return {"raw_objects": int(raw_count), "document_versions": int(document_count)}

    def begin_adapter_run(
        self,
        *,
        source_id: str,
        adapter_id: str,
        adapter_version: str,
        trigger: str = "schedule",
    ) -> Dict[str, Any]:
        """Open one source-scoped run before any network request is made."""
        source = self.registry.get(source_id)
        if source.get("adapter_id") != adapter_id:
            raise DataAssetError(f"适配器与来源契约不一致: {source_id}/{adapter_id}")
        if source.get("adapter_version") != adapter_version:
            raise DataAssetError(
                f"适配器版本与来源契约不一致: {source_id}/{adapter_version}"
            )
        run_id = uuid.uuid4().hex
        started_at = utc_now()
        cursor_before = self.get_source_cursor(source_id)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO adapter_runs (
                    run_id, source_id, adapter_id, adapter_version, trigger,
                    state, started_at, cursor_before_json, metrics_json
                ) VALUES (%s, %s, %s, %s, %s, 'running', %s, %s, '{}')
                """,
                (
                    run_id,
                    source_id,
                    adapter_id,
                    adapter_version,
                    trigger,
                    started_at,
                    _json(cursor_before) if cursor_before else None,
                ),
            )
        return self.get_adapter_run(run_id)

    def finish_adapter_run(
        self,
        run_id: str,
        *,
        state: str,
        metrics: Optional[Mapping[str, Any]] = None,
        cursor: Optional[Mapping[str, Any]] = None,
        errors: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Any]:
        """Persist one terminal adapter result and advance its cursor only on success."""
        if state not in {"healthy", "degraded", "failed", "cancelled"}:
            raise ValueError(f"不支持的适配器终态: {state}")
        current = self.get_adapter_run(run_id)
        values = dict(metrics or {})
        fields = {
            "entrypoints_total",
            "entrypoints_succeeded",
            "detail_discovered",
            "detail_fetched",
            "documents_emitted",
            "evidence_archived",
            "failures",
        }
        normalized = {field: max(0, int(values.get(field, 0) or 0)) for field in fields}
        finished_at = utc_now()
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE adapter_runs SET
                    state = %s, finished_at = %s, entrypoints_total = %s,
                    entrypoints_succeeded = %s, detail_discovered = %s,
                    detail_fetched = %s, documents_emitted = %s,
                    evidence_archived = %s, failures = %s, cursor_after_json = %s,
                    error_summary_json = %s, metrics_json = %s
                WHERE run_id = %s
                """,
                (
                    state,
                    finished_at,
                    normalized["entrypoints_total"],
                    normalized["entrypoints_succeeded"],
                    normalized["detail_discovered"],
                    normalized["detail_fetched"],
                    normalized["documents_emitted"],
                    normalized["evidence_archived"],
                    normalized["failures"],
                    _json(cursor) if cursor else None,
                    _json(list(errors or [])) if errors else None,
                    _json(values),
                    run_id,
                ),
            )
        if state == "healthy" and cursor:
            self.set_source_cursor(
                source_id=current["source_id"],
                adapter_id=current["adapter_id"],
                adapter_version=current["adapter_version"],
                cursor=cursor,
            )
        return self.get_adapter_run(run_id)

    def get_adapter_run(self, run_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM adapter_runs WHERE run_id = %s", (run_id,)
            ).fetchone()
        if not row:
            raise KeyError(run_id)
        return self._adapter_run_row(row)

    def latest_adapter_run(self, source_id: str) -> Optional[Dict[str, Any]]:
        self.registry.get(source_id)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM adapter_runs WHERE source_id = %s
                ORDER BY started_at DESC LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        return self._adapter_run_row(row) if row else None

    def list_adapter_runs(self, source_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 500))
        parameters: List[Any] = []
        where = ""
        if source_id:
            self.registry.get(source_id)
            where = "WHERE source_id = %s"
            parameters.append(source_id)
        parameters.append(bounded)
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM adapter_runs {where} ORDER BY started_at DESC LIMIT %s",
                parameters,
            ).fetchall()
        return [self._adapter_run_row(row) for row in rows]

    def recover_interrupted_adapter_runs(self) -> int:
        """Close runs left open by a previous collector process before scheduling again."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT run_id FROM adapter_runs WHERE state = 'running'"
            ).fetchall()
            now = utc_now()
            connection.executemany(
                """
                UPDATE adapter_runs SET state = 'failed', finished_at = %s, failures = failures + 1,
                    error_summary_json = %s WHERE run_id = %s
                """,
                [
                    (now, _json(["采集器重启前运行未正常结束"]), row["run_id"])
                    for row in rows
                ],
            )
        return len(rows)

    def get_source_cursor(self, source_id: str) -> Optional[Dict[str, Any]]:
        source = self.registry.get(source_id)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT adapter_id, adapter_version, cursor_json
                FROM source_cursors WHERE source_id = %s
                """,
                (source_id,),
            ).fetchone()
        if not row:
            return None
        if row["adapter_id"] != source["adapter_id"] or row["adapter_version"] != source["adapter_version"]:
            return None
        return json.loads(row["cursor_json"])

    def set_source_cursor(
        self,
        *,
        source_id: str,
        adapter_id: str,
        adapter_version: str,
        cursor: Mapping[str, Any],
    ) -> None:
        source = self.registry.get(source_id)
        if source.get("adapter_id") != adapter_id or source.get("adapter_version") != adapter_version:
            raise DataAssetError(f"游标与当前适配器版本不一致: {source_id}/{adapter_id}/{adapter_version}")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO source_cursors (
                    source_id, adapter_id, adapter_version, cursor_json, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(source_id) DO UPDATE SET
                    adapter_id = excluded.adapter_id,
                    adapter_version = excluded.adapter_version,
                    cursor_json = excluded.cursor_json,
                    updated_at = excluded.updated_at
                """,
                (source_id, adapter_id, adapter_version, _json(dict(cursor)), utc_now()),
            )

    def request_adapter_run(
        self,
        source_id: str,
        *,
        requested_by: str = "operator",
    ) -> Dict[str, Any]:
        """Queue one source-scoped run, deduplicating active requests."""
        source = self.registry.get(source_id)
        if not source.get("enabled"):
            raise DataAssetError(f"来源未启用: {source_id}")
        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT * FROM adapter_run_requests
                WHERE source_id = %s AND state IN ('queued', 'running')
                ORDER BY requested_at ASC LIMIT 1
                """,
                (source_id,),
            ).fetchone()
            if existing:
                return self._adapter_request_row(existing)
            request_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO adapter_run_requests (
                    request_id, source_id, requested_by, state, requested_at
                ) VALUES (%s, %s, %s, 'queued', %s)
                ON CONFLICT DO NOTHING
                """,
                (request_id, source_id, requested_by[:100], utc_now()),
            )
            row = connection.execute(
                """
                SELECT * FROM adapter_run_requests
                WHERE source_id = %s AND state IN ('queued', 'running')
                ORDER BY requested_at ASC LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        return self._adapter_request_row(row)

    def active_adapter_run_request(self, source_id: str) -> Optional[Dict[str, Any]]:
        self.registry.get(source_id)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM adapter_run_requests
                WHERE source_id = %s AND state IN ('queued', 'running')
                ORDER BY requested_at ASC LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        return self._adapter_request_row(row) if row else None

    def claim_adapter_run_request(self) -> Optional[Dict[str, Any]]:
        """Atomically claim the oldest manual collection request."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM adapter_run_requests
                WHERE state = 'queued' ORDER BY requested_at ASC
                LIMIT 1 FOR UPDATE SKIP LOCKED
                """
            ).fetchone()
            if not row:
                return None
            claimed_at = utc_now()
            updated = connection.execute(
                """
                UPDATE adapter_run_requests SET state = 'running', claimed_at = %s
                WHERE request_id = %s AND state = 'queued'
                """,
                (claimed_at, row["request_id"]),
            )
            if updated.rowcount != 1:
                return None
            claimed = connection.execute(
                "SELECT * FROM adapter_run_requests WHERE request_id = %s",
                (row["request_id"],),
            ).fetchone()
        return self._adapter_request_row(claimed)

    def recover_interrupted_adapter_run_requests(self) -> int:
        """Requeue manual requests claimed by a collector that stopped mid-run."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT request_id FROM adapter_run_requests WHERE state = 'running'"
            ).fetchall()
            connection.executemany(
                """
                UPDATE adapter_run_requests SET state = 'queued', claimed_at = NULL,
                    error = '采集器重启，任务已自动重新排队'
                WHERE request_id = %s
                """,
                [(row["request_id"],) for row in rows],
            )
        return len(rows)

    def finish_adapter_run_request(
        self,
        request_id: str,
        *,
        run_id: Optional[str],
        result_state: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        if result_state not in {"healthy", "degraded", "failed", "cancelled"}:
            raise ValueError(f"不支持的请求终态: {result_state}")
        with self._connection() as connection:
            updated = connection.execute(
                """
                UPDATE adapter_run_requests SET state = 'completed', finished_at = %s,
                    run_id = %s, result_state = %s, error = %s
                WHERE request_id = %s AND state = 'running'
                """,
                (utc_now(), run_id, result_state, error, request_id),
            )
            if updated.rowcount != 1:
                raise DataAssetError(f"采集请求不在运行态: {request_id}")
            row = connection.execute(
                "SELECT * FROM adapter_run_requests WHERE request_id = %s",
                (request_id,),
            ).fetchone()
        return self._adapter_request_row(row)

    def quarantine_generic_snapshots(self) -> int:
        """Keep archived snapshots but remove them from the formal search corpus."""
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT content_version_id FROM standard_documents
                WHERE active = 1 AND parser_version LIKE %s
                """,
                ("qsou-generic-html/%",),
            ).fetchall()
            ids = [row["content_version_id"] for row in rows]
            if ids:
                now = utc_now()
                connection.executemany(
                    "UPDATE standard_documents SET active = 0, superseded_at = %s WHERE content_version_id = %s",
                    [(now, content_version_id) for content_version_id in ids],
                )
                connection.executemany(
                    """
                    UPDATE processing_outbox SET state = 'filtered',
                        last_error = '通用页面快照不进入正式情报索引', updated_at = %s
                    WHERE content_version_id = %s
                    """,
                    [(now, content_version_id) for content_version_id in ids],
                )
        return len(ids)

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
            where = "WHERE source_id = %s"
            parameters.append(source_id)
        parameters.extend([bounded, offset])

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM raw_objects {where}
                ORDER BY first_fetched_at DESC LIMIT %s OFFSET %s
                """,
                parameters,
            ).fetchall()
        return [self._evidence_row(row) for row in rows]

    def get_evidence(self, raw_object_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM raw_objects WHERE raw_object_id = %s",
                (raw_object_id,),
            ).fetchone()
        if not row:
            raise KeyError(raw_object_id)
        return self._evidence_row(row)

    def evidence_body_path(self, raw_object_id: str) -> Path:
        evidence = self.get_evidence(raw_object_id)
        try:
            return self.object_store.materialize(
                evidence["body_path"],
                self.object_cache_dir,
                evidence["content_hash"],
            )
        except ObjectStorageError as exc:
            raise DataAssetError(f"原始证据文件不可用: {raw_object_id}: {exc}") from exc

    def evidence_has_document(self, raw_object_id: str) -> bool:
        """Return whether one immutable response is already linked to a document."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM document_evidence WHERE raw_object_id = %s LIMIT 1",
                (raw_object_id,),
            ).fetchone()
        return row is not None

    def get_document(self, content_version_id: str) -> Dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT document_json FROM standard_documents WHERE content_version_id = %s",
                (content_version_id,),
            ).fetchone()
            evidence_rows = connection.execute(
                """
                SELECT raw_object_id FROM document_evidence
                WHERE content_version_id = %s ORDER BY observed_at ASC
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
            clauses.append("(LOWER(title) LIKE %s OR LOWER(content) LIKE %s)")
            wildcard = f"%{term}%"
            parameters.extend([wildcard, wildcard])
        where = "active = 1 AND " + " AND ".join(clauses)
        if source_id:
            self.registry.get(source_id)
            where += " AND source_id = %s"
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
                LIMIT %s OFFSET %s
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
            where = "WHERE source_id = %s"
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
                FROM standard_documents WHERE content_version_id = %s
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
                    "SELECT document_json FROM standard_documents WHERE content_version_id = %s",
                    (content_version_id,),
                ).fetchone()
                if not row:
                    continue
                document = json.loads(row["document_json"])
                document[field] = value
                connection.execute(
                    f"""
                    UPDATE standard_documents
                    SET {field} = %s, document_json = %s
                    WHERE content_version_id = %s
                    """,
                    (value, _json(document), content_version_id),
                )

    def _raw_exists(self, raw_object_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM raw_objects WHERE raw_object_id = %s",
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
                SET state = %s, attempts = attempts + %s, task_id = COALESCE(%s, task_id),
                    last_error = %s, updated_at = %s
                WHERE content_version_id = %s
                """,
                [
                    (state, attempt_delta, task_id, error, now, content_version_id)
                    for content_version_id in ids
                ],
            )

    @staticmethod
    def _adapter_run_row(row: Mapping[str, Any]) -> Dict[str, Any]:
        value = dict(row)
        for source_key, target_key in (
            ("cursor_before_json", "cursor_before"),
            ("cursor_after_json", "cursor_after"),
            ("error_summary_json", "errors"),
            ("metrics_json", "metrics"),
        ):
            raw = value.pop(source_key)
            value[target_key] = json.loads(raw) if raw else None
        return value

    @staticmethod
    def _adapter_request_row(row: Mapping[str, Any]) -> Dict[str, Any]:
        return dict(row)

    @staticmethod
    def _safe_headers(headers: Mapping[Any, Any]) -> Dict[str, str]:
        safe: Dict[str, str] = {}
        for raw_key, raw_value in headers.items():
            key = raw_key.decode("latin-1") if isinstance(raw_key, bytes) else str(raw_key)
            key = normalize_catalog_value(key)
            normalized = key.lower()
            if normalized not in SAFE_RESPONSE_HEADERS:
                continue
            if isinstance(raw_value, (list, tuple)):
                values = [value.decode("latin-1") if isinstance(value, bytes) else str(value) for value in raw_value]
                value = ", ".join(values)
            else:
                value = raw_value.decode("latin-1") if isinstance(raw_value, bytes) else str(raw_value)
            safe[normalized] = normalize_catalog_value(value)
        return safe

    def _evidence_row(self, row: Mapping[str, Any]) -> Dict[str, Any]:
        value = dict(row)
        value["response_headers"] = json.loads(value.pop("response_headers_json"))
        return value
