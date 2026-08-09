from __future__ import annotations

from urllib.parse import urlencode, urljoin

from .base import AnnouncementHTMLAdapter, DocumentReference, RequestSpec, ResponsePayload, json_body, normalize_text


class SseAdapter(AnnouncementHTMLAdapter):
    source_id = "sse"
    adapter_id = "sse-announcements"
    version = "1.0.0"
    link_patterns = (r"/disclosure/.+\.pdf(?:$|\?)",)

    def initial_requests(self, cursor=None):
        del cursor
        params = {
            "isPagination": "true",
            "productId": "",
            "keyWord": "",
            "securityType": "0101,120100,020100,020200,120200",
            "reportType2": "DQBG",
            "reportType": "ALL",
            "pageHelp.pageSize": "30",
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.endPage": "1",
        }
        return [
            RequestSpec(
                url="https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?" + urlencode(params),
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://www.sse.com.cn/disclosure/listedinfo/announcement/",
                },
            )
        ]

    def discover(self, response: ResponsePayload):
        payload = json_body(response)
        page_help = payload.get("pageHelp") if isinstance(payload.get("pageHelp"), dict) else {}
        rows = page_help.get("data") or payload.get("result") or []
        references = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("URL"):
                continue
            url = urljoin("https://www.sse.com.cn", str(row["URL"]))
            references.append(
                DocumentReference(
                    url=url,
                    source_document_id=f"{row.get('SECURITY_CODE', '')}:{row.get('SSEDATE', '')}:{url.rsplit('/', 1)[-1]}",
                    title=normalize_text(row.get("TITLE")),
                    published_at=normalize_text(row.get("SSEDATE")) or None,
                    document_type="announcement",
                    metadata={
                        "company_code": row.get("SECURITY_CODE"),
                        "company_name": row.get("SECURITY_NAME"),
                        "announcement_type": row.get("BULLETIN_TYPE") or row.get("BULLETIN_HEADING"),
                    },
                )
            )
        return references
