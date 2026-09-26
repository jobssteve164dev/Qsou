"""Replay archived responses through their registered source adapters."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Mapping

from qsou_crawler.adapters import AdapterRegistry, DocumentReference, ResponsePayload


_REFERENCE_FIELDS = {field.name for field in fields(DocumentReference)}


def _reference_from_context(
    adapter,
    evidence: Mapping[str, Any],
    context: Mapping[str, Any],
) -> DocumentReference:
    url = str(evidence["url"])
    metadata = {
        key: value
        for key, value in context.items()
        if key not in _REFERENCE_FIELDS and key != "qsou_request_kind"
    }
    return DocumentReference(
        url=url,
        source_document_id=str(
            context.get("source_document_id") or adapter.reference_id(url)
        ),
        title=str(context.get("title") or adapter.reference_id(url)),
        published_at=context.get("published_at"),
        document_type=str(
            context.get("document_type") or adapter.document_type
        ),
        metadata=metadata,
    )


def _documents_from_evidence(adapter, response, evidence, context):
    request_kind = str(context.get("qsou_request_kind") or "")
    if request_kind == "media":
        return []

    if request_kind == "detail" or (
        not request_kind and adapter.accepts_detail_url(response.url)
    ):
        reference = _reference_from_context(adapter, evidence, context)
        document = adapter.parse_document(response, reference)
        return [document] if document else []

    references = adapter.discover(response)
    inline = [
        reference
        for reference in references
        if reference.metadata.get("inline_document")
        or (
            reference.url == response.url
            and reference.metadata.get("inline_release")
        )
    ]
    documents = [
        document
        for reference in inline
        if (document := adapter.parse_document(response, reference))
    ]
    if documents or not adapter.accepts_detail_url(response.url):
        return documents

    matching = next(
        (reference for reference in references if reference.url == response.url),
        None,
    )
    reference = matching or _reference_from_context(adapter, evidence, context)
    document = adapter.parse_document(response, reference)
    return [document] if document else []


def replay_evidence_batch(store, adapters=None, *, batch_size: int = 50) -> dict[str, int]:
    """Advance one bounded batch of durable raw-evidence replay work."""
    registry = adapters or AdapterRegistry(store.registry)
    evidence_batch = store.claim_evidence_replay(batch_size)
    result = {"claimed": len(evidence_batch), "parsed": 0, "skipped": 0, "failed": 0}

    for evidence in evidence_batch:
        raw_object_id = str(evidence["raw_object_id"])
        try:
            store.start_evidence_replay(raw_object_id)
            if store.evidence_has_document(raw_object_id):
                store.complete_evidence_replay(raw_object_id, "parsed")
                result["parsed"] += 1
                continue
            if not 200 <= int(evidence["status_code"]) < 300:
                store.complete_evidence_replay(
                    raw_object_id,
                    "skipped",
                    f"HTTP {evidence['status_code']}",
                )
                result["skipped"] += 1
                continue

            context = dict(evidence.get("request_context") or {})
            adapter = registry.create(str(evidence["source_id"]))
            response = ResponsePayload(
                url=str(evidence["url"]),
                body=store.evidence_body_path(raw_object_id).read_bytes(),
                status=int(evidence["status_code"]),
                content_type=str(evidence.get("content_type") or "application/octet-stream"),
                encoding=evidence.get("encoding"),
                metadata=context,
            )
            documents = _documents_from_evidence(
                adapter,
                response,
                evidence,
                context,
            )
            if not documents:
                store.complete_evidence_replay(
                    raw_object_id,
                    "skipped",
                    "来源适配器未从该响应产出标准文档",
                )
                result["skipped"] += 1
                continue

            for document in documents:
                metadata = dict(document.get("metadata") or {})
                metadata.update(
                    {
                        "raw_object_id": raw_object_id,
                        "source_id": evidence["source_id"],
                        "fetched_at": evidence["last_fetched_at"],
                    }
                )
                store.register_document(
                    {
                        **document,
                        "raw_object_id": raw_object_id,
                        "fetched_at": evidence["last_fetched_at"],
                        "metadata": metadata,
                    }
                )
            store.complete_evidence_replay(raw_object_id, "parsed")
            result["parsed"] += 1
        except Exception as exc:
            store.complete_evidence_replay(
                raw_object_id,
                "failed",
                f"{type(exc).__name__}: {exc}"[:1000],
            )
            result["failed"] += 1

    return result
