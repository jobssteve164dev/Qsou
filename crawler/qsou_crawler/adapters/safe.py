"""State Administration of Foreign Exchange official data-file adapter."""

import re
from urllib.parse import urljoin

from .base import DocumentReference, RequestSpec, normalize_text, parse_html
from .official_statistics import OfficialStatisticsAdapter


class SafeAdapter(OfficialStatisticsAdapter):
    source_id = "safe"
    adapter_id = "safe-statistical-releases"
    version = "1.0.0"
    link_patterns = (
        r"safe\.gov\.cn/safe/file/file/\d{8}/[a-f0-9]+\.(?:xlsx?|csv|pdf)(?:$|\?)",
    )

    def listing_requests(self, response):
        if response.metadata.get("safe_stage") == "release":
            return []
        parser = parse_html(response.text)
        requests = []
        seen = set()
        for href, _ in parser.links:
            url = urljoin(response.url, href)
            if url in seen or not re.search(r"/safe/\d{4}/\d{4}/\d+\.html$", url):
                continue
            seen.add(url)
            requests.append(
                RequestSpec(url=url, metadata={"safe_stage": "release"})
            )
        return requests

    def discover(self, response):
        if response.metadata.get("safe_stage") != "release":
            return []
        parser = parse_html(response.text)
        references = []
        seen = set()
        published = None
        match = re.search(r"/safe/(\d{4})/(\d{2})(\d{2})/", response.url)
        if match:
            published = f"{match.group(1)}-{match.group(2)}-{match.group(3)}T00:00:00+08:00"
        for href, link_text in parser.links:
            url = urljoin(response.url, href)
            if url in seen or not self.accepts_detail_url(url):
                continue
            seen.add(url)
            references.append(
                DocumentReference(
                    url=url,
                    source_document_id=self.reference_id(url),
                    title=normalize_text(link_text) or self.reference_id(url),
                    published_at=published,
                    document_type=self.document_type,
                    metadata={"release_page_url": response.url},
                )
            )
        if not references:
            title = normalize_text(" ".join(parser.heading_parts) or " ".join(parser.title_parts))
            references.append(
                DocumentReference(
                    url=response.url,
                    source_document_id=self.reference_id(response.url),
                    title=title or self.reference_id(response.url),
                    published_at=published,
                    document_type=self.document_type,
                    metadata={"release_page_url": response.url, "inline_release": True},
                )
            )
        return references
