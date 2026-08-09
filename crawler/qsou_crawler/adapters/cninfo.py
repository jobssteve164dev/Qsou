from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from .base import AnnouncementHTMLAdapter, DocumentReference, RequestSpec, ResponsePayload, json_body, normalize_text


class CninfoAdapter(AnnouncementHTMLAdapter):
    source_id = "cninfo"
    adapter_id = "cninfo-announcements"
    version = "1.0.0"
    link_patterns = (r"/finalpage/.+\.pdf(?:$|\?)",)

    def initial_requests(self, cursor=None):
        del cursor
        today = datetime.now(timezone.utc).date()
        begin = today - timedelta(days=14)
        form = urlencode(
            {
                "pageNum": "1",
                "pageSize": "30",
                "column": "szse",
                "tabName": "fulltext",
                "plate": "",
                "stock": "",
                "searchkey": "",
                "secid": "",
                "category": "",
                "trade": "",
                "seDate": f"{begin.isoformat()}~{today.isoformat()}",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            }
        ).encode("utf-8")
        return [
            RequestSpec(
                url="https://www.cninfo.com.cn/new/hisAnnouncement/query",
                method="POST",
                body=form,
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": "https://www.cninfo.com.cn/new/disclosure/",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        ]

    def discover(self, response: ResponsePayload):
        payload = json_body(response)
        references = []
        for row in payload.get("announcements") or []:
            if not isinstance(row, dict) or not row.get("adjunctUrl"):
                continue
            path = str(row["adjunctUrl"]).lstrip("/")
            published = row.get("announcementTime")
            if isinstance(published, (int, float)):
                published = datetime.fromtimestamp(published / 1000, tz=timezone.utc).isoformat()
            title = normalize_text(row.get("announcementTitle"))
            references.append(
                DocumentReference(
                    url=f"https://static.cninfo.com.cn/{path}",
                    source_document_id=str(row.get("announcementId") or path),
                    title=title,
                    published_at=normalize_text(published) or None,
                    document_type="announcement",
                    metadata={
                        "company_code": row.get("secCode"),
                        "company_name": row.get("secName"),
                    },
                )
            )
        return references
