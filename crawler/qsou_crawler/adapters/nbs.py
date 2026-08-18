"""National Bureau of Statistics official release adapter."""

import re
from urllib.parse import urljoin

from .base import DocumentReference, normalize_text, parse_html
from .official_statistics import OfficialStatisticsAdapter


class NbsAdapter(OfficialStatisticsAdapter):
    source_id = "nbs"
    adapter_id = "nbs-statistical-releases"
    version = "1.0.0"
    link_patterns = (r"stats\.gov\.cn/sj/zxfb/\d{6}/t\d+_\d+\.html(?:$|\?)",)

    def discover(self, response):
        parser = parse_html(response.text)
        references = []
        seen = set()
        for href, link_text in parser.links:
            url = urljoin(response.url, href)
            if url in seen or not self.accepts_detail_url(url):
                continue
            seen.add(url)
            match = re.search(r"/t(\d+)_(\d+)\.html", url)
            source_document_id = "-".join(match.groups()) if match else self.reference_id(url)
            references.append(
                DocumentReference(
                    url=url,
                    source_document_id=source_document_id,
                    title=normalize_text(link_text),
                    document_type=self.document_type,
                    metadata={"release_family": "latest_statistical_release"},
                )
            )
        return references
