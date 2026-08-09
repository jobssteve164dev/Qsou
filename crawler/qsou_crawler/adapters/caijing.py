from datetime import datetime, timezone

from .base import DocumentReference, NewsHTMLAdapter, json_body, normalize_text, parse_html


class CaijingAdapter(NewsHTMLAdapter):
    source_id = "caijing"
    adapter_id = "caijing-news"
    version = "1.0.0"
    link_patterns = (
        r"[a-z]+\.caijing\.com\.cn/\d{8}/\d+\.shtml(?:$|\?)",
        r"caijing\.com\.cn/\d{4}-\d{2}-\d{2}/\d+\.shtml(?:$|\?)",
    )
    excluded_patterns = (r"/video/", r"javascript:")

    def discover(self, response):
        payload = json_body(response)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        references = []
        for row in [*(data.get("slider") or []), *(data.get("lists") or [])]:
            if not isinstance(row, dict) or not row.get("url") or not row.get("contentid"):
                continue
            published = row.get("published")
            if str(published).isdigit():
                published = datetime.fromtimestamp(int(published), tz=timezone.utc).isoformat()
            references.append(
                DocumentReference(
                    url=str(row["url"]).replace("http://", "https://", 1),
                    source_document_id=str(row["contentid"]),
                    title=normalize_text(row.get("title")),
                    published_at=normalize_text(published) or None,
                    document_type="news",
                    metadata={"content_granularity": "full_text"},
                )
            )
        return references

    def parse_document(self, response, reference):
        payload = json_body(response)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        parser = parse_html(str(data.get("content") or ""))
        content = normalize_text("\n".join(parser.semantic_blocks or parser.fallback_blocks))
        title = normalize_text(data.get("title") or reference.title)
        if len(title) < 4 or len(content) < 80:
            return None
        published = data.get("published")
        if str(published).isdigit():
            published = datetime.fromtimestamp(int(published), tz=timezone.utc).isoformat()
        return {
            "source_document_id": str(data.get("contentid") or reference.source_document_id),
            "type": "news",
            "title": title[:500],
            "content": content[:500_000],
            "url": str(data.get("url") or response.url),
            "source": self.source.get("source_name", self.source_id),
            "source_id": self.source_id,
            "source_published_at": normalize_text(published) or reference.published_at,
            "parser_version": f"{self.adapter_id}/{self.version}",
            "metadata": {
                "adapter_id": self.adapter_id,
                "adapter_version": self.version,
                "extraction": "official_mobile_json",
                "content_granularity": "full_text",
                "publisher_source": data.get("source"),
                "editor": data.get("editor"),
            },
        }
