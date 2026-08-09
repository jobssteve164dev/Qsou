"""Create searchable page snapshots for archived HTML not parsed by a spider."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from qsou_data import DataAssetStore


PARSER_VERSION = "qsou-generic-html/1"
MIN_CONTENT_LENGTH = 80
MAX_CONTENT_LENGTH = 200_000
BLOCK_PAGE_MARKERS = (
    "just a moment",
    "access denied",
    "403 forbidden",
    "安全验证",
    "请输入验证码",
)


class _PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self.in_title = True
        if lowered in {"script", "style", "noscript", "svg"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self.in_title = False
        if lowered in {"script", "style", "noscript", "svg"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif not self.ignored_depth:
            normalized = " ".join(data.split())
            if normalized:
                self.text_parts.append(normalized)


def _decode(body: bytes, encoding: str | None) -> str:
    for candidate in (encoding, "utf-8", "gb18030"):
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def _extract(html: str, url: str) -> tuple[str, str]:
    parser = _PageTextParser()
    parser.feed(html)
    content = "\n".join(parser.text_parts)
    title = " ".join("".join(parser.title_parts).split())
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    return (title or first_line or urlsplit(url).netloc)[:200], content


def index_pending_html_evidence(
    store: DataAssetStore | None = None,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    """Index useful HTML snapshots while preserving their raw-evidence identity."""
    asset_store = store or DataAssetStore()
    indexed = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for evidence in asset_store.list_evidence(limit=limit):
        raw_object_id = evidence["raw_object_id"]
        url = evidence["url"]
        content_type = str(evidence.get("content_type") or "").lower()
        if (
            asset_store.evidence_has_document(raw_object_id)
            or not 200 <= int(evidence["status_code"]) < 300
            or "html" not in content_type
            or urlsplit(url).path.lower().endswith("/robots.txt")
        ):
            skipped += 1
            continue

        try:
            html = _decode(
                asset_store.evidence_body_path(raw_object_id).read_bytes(),
                evidence.get("encoding"),
            )
            title, content = _extract(html, url)
            normalized_probe = f"{title}\n{content[:1000]}".lower()
            if len(content) < MIN_CONTENT_LENGTH or any(
                marker in normalized_probe for marker in BLOCK_PAGE_MARKERS
            ):
                skipped += 1
                continue
            content = content[:MAX_CONTENT_LENGTH]

            document = asset_store.register_document(
                {
                    "source_document_id": url,
                    "raw_object_id": raw_object_id,
                    "source_id": evidence["source_id"],
                    "type": "web_snapshot",
                    "title": title,
                    "content": content,
                    "url": url,
                    "fetched_at": evidence["last_fetched_at"],
                    "parser_version": PARSER_VERSION,
                    "metadata": {"extraction": "generic_html_snapshot"},
                }
            )
            asset_store.mark_indexed([document["content_version_id"]])
            indexed += 1
        except Exception as exc:  # one malformed response must not abort the cycle
            errors.append({"raw_object_id": raw_object_id, "error": str(exc)})

    return {"indexed": indexed, "skipped": skipped, "errors": errors}
