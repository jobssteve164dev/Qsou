"""SEC EDGAR public filing adapter using the regulator's automated-access paths."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from urllib.parse import urljoin

from .base import (
    DocumentReference,
    RequestSpec,
    ResponsePayload,
    SourceAdapter,
    normalize_text,
    parse_html,
)


_SUPPORTED_FORMS = {"8-K", "10-K", "10-Q", "20-F", "40-F", "6-K"}
_ACCESSION_RE = re.compile(r"(?P<accession>\d{10}-\d{2}-\d{6})\.txt$")
_DECLARED_HEADERS = {
    "User-Agent": "QSou Investment Data qsou-contact@szlk.uk",
    "Accept-Encoding": "gzip, deflate",
}


class SecEdgarAdapter(SourceAdapter):
    source_id = "sec-edgar"
    adapter_id = "sec-edgar-filings"
    version = "1.0.0"
    document_type = "filing"

    def initial_requests(
        self,
        cursor: Optional[Mapping[str, Any]] = None,
    ) -> list[RequestSpec]:
        del cursor
        now = datetime.now(timezone.utc)
        quarter = ((now.month - 1) // 3) + 1
        return [
            RequestSpec(
                url=(
                    "https://www.sec.gov/Archives/edgar/daily-index/"
                    f"{now.year}/QTR{quarter}/index.json"
                ),
                headers=_DECLARED_HEADERS,
                metadata={"sec_stage": "quarter_index"},
            )
        ]

    def listing_requests(self, response: ResponsePayload) -> list[RequestSpec]:
        if response.metadata.get("sec_stage") != "quarter_index":
            return []
        payload = json.loads(response.text)
        items = payload.get("directory", {}).get("item", [])
        names = sorted(
            str(item.get("name") or "")
            for item in items
            if re.fullmatch(r"master\.\d{8}\.idx", str(item.get("name") or ""))
        )
        if not names:
            raise ValueError("SEC EDGAR 季度目录没有可用的 master 索引")
        return [
            RequestSpec(
                url=urljoin(response.url, names[-1]),
                headers=_DECLARED_HEADERS,
                metadata={"sec_stage": "daily_master", "master_index": names[-1]},
            )
        ]

    def discover(self, response: ResponsePayload) -> list[DocumentReference]:
        if response.metadata.get("sec_stage") != "daily_master":
            return []
        references: list[DocumentReference] = []
        for line in response.text.splitlines():
            parts = [part.strip() for part in line.split("|")]
            if len(parts) != 5:
                continue
            cik, company, form, filed_at, filename = parts
            if form not in _SUPPORTED_FORMS:
                continue
            match = _ACCESSION_RE.search(filename)
            if not match:
                continue
            accession = match.group("accession")
            references.append(
                DocumentReference(
                    url=f"https://www.sec.gov/Archives/{filename.lstrip('/')}",
                    source_document_id=accession,
                    title=normalize_text(f"{company} {form} filing"),
                    published_at=f"{filed_at}T00:00:00Z" if filed_at else None,
                    document_type=self.document_type,
                    metadata={
                        "cik": cik,
                        "company_name": company,
                        "form_type": form,
                        "accession_number": accession,
                        "master_index": response.metadata.get("master_index"),
                    },
                )
            )
        return references

    def detail_request(self, reference: DocumentReference) -> RequestSpec:
        specification = super().detail_request(reference)
        return RequestSpec(
            url=specification.url,
            kind=specification.kind,
            headers=_DECLARED_HEADERS,
            metadata=specification.metadata,
        )

    def parse_document(
        self,
        response: ResponsePayload,
        reference: DocumentReference,
    ) -> Optional[dict[str, Any]]:
        parser = parse_html(response.text)
        blocks = parser.semantic_blocks or parser.fallback_blocks
        content = normalize_text("\n".join(dict.fromkeys(blocks)))
        if len(content) < 80:
            content = normalize_text(response.text)
        title = normalize_text(reference.title)
        if len(title) < 4 or len(content) < 80:
            return None
        return {
            "source_document_id": reference.source_document_id,
            "type": self.document_type,
            "title": title[:500],
            "content": content[:500_000],
            "url": response.url,
            "source": self.source.get("source_name", self.source_id),
            "source_id": self.source_id,
            "source_published_at": reference.published_at,
            "parser_version": f"{self.adapter_id}/{self.version}",
            "metadata": {
                "adapter_id": self.adapter_id,
                "adapter_version": self.version,
                "extraction": "sec_complete_submission_text",
                "content_granularity": "full_filing_submission",
                **dict(reference.metadata),
            },
        }
