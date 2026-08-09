from __future__ import annotations

from urllib.parse import urlencode

from .base import AnnouncementHTMLAdapter, DocumentReference, RequestSpec, ResponsePayload, json_body, normalize_text


class SzseAdapter(AnnouncementHTMLAdapter):
    source_id = "szse"
    adapter_id = "szse-announcements"
    version = "1.0.0"
    link_patterns = (r"/disc/.+\.pdf(?:$|\?)", r"/disclosure/.+\.pdf(?:$|\?)")

    def initial_requests(self, cursor=None):
        del cursor
        params = urlencode({"pageSize": 50, "pageNum": 1, "plateCode": "szse"})
        return [
            RequestSpec(
                url=f"https://www.szse.cn/api/disc/announcement/detailinfo?{params}",
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://www.szse.cn/disclosure/listed/notice/index.html",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        ]

    def discover(self, response: ResponsePayload):
        payload = json_body(response)
        references = []
        for company in payload.get("data") or []:
            if not isinstance(company, dict):
                continue
            for row in company.get("announList") or []:
                if not isinstance(row, dict) or not row.get("attachPath"):
                    continue
                path = str(row["attachPath"])
                url = path if path.startswith("http") else f"https://disc.static.szse.cn{path}"
                references.append(
                    DocumentReference(
                        url=url,
                        source_document_id=str(row.get("annId") or row.get("id") or url),
                        title=normalize_text(row.get("title")),
                        published_at=normalize_text(row.get("publishTime")) or None,
                        document_type="announcement",
                        metadata={
                            "company_code": company.get("secCode"),
                            "company_name": company.get("secName"),
                            "announcement_type": row.get("bigCategoryName"),
                        },
                    )
                )
        return references
