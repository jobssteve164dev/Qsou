"""Versioned source-adapter contract independent from the crawler runtime."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree


_SPACE_RE = re.compile(r"\s+")
_DATE_RE = re.compile(r"(20\d{2})[年\-/](\d{1,2})[月\-/](\d{1,2})(?:[日T\s]+(\d{1,2}):?(\d{2})?:?(\d{2})?)?")


def normalize_text(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "")).strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decode_body(body: bytes, encoding: Optional[str] = None) -> str:
    for candidate in (encoding, "utf-8", "gb18030"):
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RequestSpec:
    url: str
    kind: str = "listing"
    method: str = "GET"
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentReference:
    url: str
    source_document_id: str = ""
    title: str = ""
    published_at: Optional[str] = None
    document_type: str = "document"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResponsePayload:
    url: str
    body: bytes
    status: int = 200
    content_type: str = "text/html"
    encoding: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return decode_body(self.body, self.encoding)


class _SemanticHTMLParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, content_container_patterns: Sequence[str] = ()) -> None:
        super().__init__(convert_charrefs=True)
        self.content_container_patterns = tuple(content_container_patterns)
        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.content_blocks: list[str] = []
        self.content_images: list[dict[str, str]] = []
        self.semantic_blocks: list[str] = []
        self.fallback_blocks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self._ignored_depth = 0
        self._semantic_depth = 0
        self._content_container_depth = 0
        self._element_stack: list[tuple[str, bool]] = []
        self._in_title = False
        self._in_heading = False
        self._block_tag: Optional[str] = None
        self._block_parts: list[str] = []
        self._link_href: Optional[str] = None
        self._link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs if key}
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        selector = normalize_text(
            " ".join((attributes.get("id", ""), attributes.get("class", "")))
        ).lower()
        is_content_container = bool(selector) and any(
            re.search(pattern, selector, re.IGNORECASE)
            for pattern in self.content_container_patterns
        )
        if tag not in self._VOID_TAGS:
            self._element_stack.append((tag, is_content_container))
        if is_content_container:
            self._content_container_depth += 1
        if tag == "img" and self._content_container_depth:
            source = normalize_text(attributes.get("src"))
            if source and not source.lower().startswith("data:"):
                self.content_images.append(
                    {
                        "src": source,
                        "alt": normalize_text(attributes.get("alt")),
                    }
                )
        if tag in {"article", "main"}:
            self._semantic_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_heading = True
        if tag in {"p", "li", "h1", "h2"} and self._block_tag is None:
            self._block_tag = tag
            self._block_parts = []
        if tag == "a" and attributes.get("href"):
            self._link_href = attributes["href"]
            self._link_parts = []
        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
                or ""
            ).lower()
            content = normalize_text(attributes.get("content"))
            if key and content:
                self.meta[key] = content
        if tag == "time" and attributes.get("datetime"):
            self.meta.setdefault("datetime", normalize_text(attributes["datetime"]))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"}:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_heading = False
        if self._block_tag == tag:
            text = normalize_text(" ".join(self._block_parts))
            if text:
                self.fallback_blocks.append(text)
                if self._semantic_depth:
                    self.semantic_blocks.append(text)
                if self._content_container_depth:
                    self.content_blocks.append(text)
            self._block_tag = None
            self._block_parts = []
        if tag == "a" and self._link_href:
            self.links.append((self._link_href, normalize_text(" ".join(self._link_parts))))
            self._link_href = None
            self._link_parts = []
        if tag in {"article", "main"} and self._semantic_depth:
            self._semantic_depth -= 1
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] != tag:
                continue
            removed = self._element_stack[index:]
            del self._element_stack[index:]
            self._content_container_depth = max(
                0,
                self._content_container_depth
                - sum(1 for _, is_container in removed if is_container),
            )
            break

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = normalize_text(data)
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if self._in_heading:
            self.heading_parts.append(text)
        if self._block_tag:
            self._block_parts.append(text)
        if self._link_href:
            self._link_parts.append(text)


def parse_html(
    html: str,
    content_container_patterns: Sequence[str] = (),
) -> _SemanticHTMLParser:
    parser = _SemanticHTMLParser(content_container_patterns)
    parser.feed(html)
    return parser


def parse_published_at(parser: _SemanticHTMLParser, html: str) -> Optional[str]:
    candidates = [
        parser.meta.get("article:published_time"),
        parser.meta.get("datepublished"),
        parser.meta.get("pubdate"),
        parser.meta.get("publishdate"),
        parser.meta.get("date"),
        parser.meta.get("datetime"),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    match = _DATE_RE.search(html[:50_000])
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    return (
        f"{int(year):04d}-{int(month):02d}-{int(day):02d}T"
        f"{int(hour or 0):02d}:{int(minute or 0):02d}:{int(second or 0):02d}+08:00"
    )


class SourceAdapter:
    """Stable contract implemented once per registered source."""

    source_id = ""
    adapter_id = ""
    version = "1.0.0"
    document_type = "document"
    link_patterns: Sequence[str] = ()
    excluded_patterns: Sequence[str] = ()
    content_container_patterns: Sequence[str] = ()

    def __init__(self, source: Mapping[str, Any]) -> None:
        self.source = dict(source)
        if self.source.get("source_id") != self.source_id:
            raise ValueError(f"来源与适配器不匹配: {self.source_id}")
        if self.source.get("adapter_id") != self.adapter_id:
            raise ValueError(f"适配器标识与来源契约不匹配: {self.adapter_id}")
        if self.source.get("adapter_version") != self.version:
            raise ValueError(f"适配器版本与来源契约不匹配: {self.adapter_id}/{self.version}")

    def initial_requests(self, cursor: Optional[Mapping[str, Any]] = None) -> list[RequestSpec]:
        del cursor
        return [RequestSpec(url=url) for url in self.source.get("entrypoints", [])]

    def discover(self, response: ResponsePayload) -> list[DocumentReference]:
        content_type = response.content_type.lower()
        if "xml" in content_type or response.url.lower().endswith((".xml", ".rss")):
            return self._discover_xml(response)
        parser = parse_html(response.text)
        references: list[DocumentReference] = []
        seen: set[str] = set()
        for href, title in parser.links:
            url = urljoin(response.url, href)
            if url in seen or not self.accepts_detail_url(url):
                continue
            seen.add(url)
            references.append(
                DocumentReference(
                    url=url,
                    source_document_id=self.reference_id(url),
                    title=title,
                    document_type=self.document_type,
                )
            )
        return references

    def detail_request(self, reference: DocumentReference) -> RequestSpec:
        return RequestSpec(
            url=reference.url,
            kind="detail",
            metadata={
                "source_document_id": reference.source_document_id,
                "title": reference.title,
                "published_at": reference.published_at,
                "document_type": reference.document_type,
                **dict(reference.metadata),
            },
        )

    def parse_document(
        self,
        response: ResponsePayload,
        reference: DocumentReference,
    ) -> Optional[dict[str, Any]]:
        content_type = response.content_type.lower()
        media_urls: list[str] = []
        parser: Optional[_SemanticHTMLParser] = None
        if "pdf" in content_type or response.url.lower().endswith(".pdf"):
            content = self._extract_pdf(response.body)
            title = normalize_text(reference.title) or self.reference_id(response.url)
            published_at = reference.published_at
        else:
            parser = parse_html(response.text, self.content_container_patterns)
            title = normalize_text(
                parser.meta.get("og:title")
                or parser.meta.get("twitter:title")
                or " ".join(parser.heading_parts)
                or reference.title
                or " ".join(parser.title_parts)
            )
            blocks = (
                parser.content_blocks
                or parser.semantic_blocks
                or parser.fallback_blocks
            )
            content = "\n".join(dict.fromkeys(blocks))
            published_at = reference.published_at or parse_published_at(parser, response.text)
            media_urls = list(
                dict.fromkeys(
                    urljoin(response.url, image["src"])
                    for image in parser.content_images
                    if urlsplit(urljoin(response.url, image["src"])).scheme in {"http", "https"}
                )
            )
        content = normalize_text(content)
        metadata = {
            "adapter_id": self.adapter_id,
            "adapter_version": self.version,
            "extraction": "structured_source_adapter",
            **dict(reference.metadata),
        }
        if len(title) < 4:
            return None
        if len(content) < 80:
            if not media_urls:
                return None
            description = normalize_text(
                parser.meta.get("description") or parser.meta.get("og:description")
            ) if parser else ""
            content = normalize_text(
                f"{title}。{description} 原文为图解报道，正文由 {len(media_urls)} 张图片组成；"
                "图像内容以来源页面为准。"
            )
            metadata.update(
                {
                    "content_format": "image_story",
                    "media_count": len(media_urls),
                    "media_urls": media_urls,
                }
            )
        if len(content) < 50:
            return None
        return {
            "source_document_id": reference.source_document_id or self.reference_id(response.url),
            "type": reference.document_type or self.document_type,
            "title": title[:500],
            "content": content[:500_000],
            "url": response.url,
            "source": self.source.get("source_name", self.source_id),
            "source_id": self.source_id,
            "source_published_at": published_at,
            "parser_version": f"{self.adapter_id}/{self.version}",
            "metadata": metadata,
        }

    def accepts_detail_url(self, url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower()
        domains = self.source.get("domains", [])
        if not any(host == domain or host.endswith(f".{domain}") for domain in domains):
            return False
        if any(re.search(pattern, url, re.IGNORECASE) for pattern in self.excluded_patterns):
            return False
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.link_patterns)

    def reference_id(self, url: str) -> str:
        path = urlsplit(url).path.rstrip("/")
        return path.rsplit("/", 1)[-1] or url

    def cursor_candidate(self, documents: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        values = list(documents)
        published = sorted(
            str(item.get("source_published_at"))
            for item in values
            if item.get("source_published_at")
        )
        return {
            "adapter_version": self.version,
            "last_successful_at": utc_now(),
            "latest_published_at": published[-1] if published else None,
            "overlap_policy": "revisit_recent_listings_and_deduplicate_by_source_document_id",
        }

    def _discover_xml(self, response: ResponsePayload) -> list[DocumentReference]:
        try:
            root = ElementTree.fromstring(response.body)
        except ElementTree.ParseError:
            return []
        references: list[DocumentReference] = []
        seen: set[str] = set()
        for item in root.findall(".//item") + root.findall(".//{*}entry"):
            link = item.findtext("link") or item.findtext("{*}link") or ""
            if not link:
                link_element = item.find("{*}link")
                link = link_element.attrib.get("href", "") if link_element is not None else ""
            url = urljoin(response.url, normalize_text(link))
            if not url or url in seen or not self.accepts_detail_url(url):
                continue
            seen.add(url)
            title = item.findtext("title") or item.findtext("{*}title") or ""
            published = (
                item.findtext("pubDate")
                or item.findtext("{*}published")
                or item.findtext("{*}updated")
            )
            references.append(
                DocumentReference(
                    url=url,
                    source_document_id=self.reference_id(url),
                    title=normalize_text(title),
                    published_at=normalize_text(published) or None,
                    document_type=self.document_type,
                )
            )
        return references

    @staticmethod
    def _extract_pdf(body: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(body), strict=False)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""


class NewsHTMLAdapter(SourceAdapter):
    document_type = "news"


class AnnouncementHTMLAdapter(SourceAdapter):
    document_type = "announcement"


def json_body(response: ResponsePayload) -> Mapping[str, Any]:
    value = json.loads(response.text)
    if not isinstance(value, Mapping):
        raise ValueError("来源接口返回的不是 JSON 对象")
    return value
