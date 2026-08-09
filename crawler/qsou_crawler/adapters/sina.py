from .base import NewsHTMLAdapter


class SinaFinanceAdapter(NewsHTMLAdapter):
    source_id = "sina-finance"
    adapter_id = "sina-finance-news"
    version = "1.1.0"
    content_container_patterns = (r"\bartibody\b",)
    link_patterns = (
        r"finance\.sina\.com\.cn/.+/doc-[a-z0-9]+\.shtml(?:$|\?)",
        r"finance\.sina\.com\.cn/roll/\d{4}-\d{2}-\d{2}/doc-[a-z0-9]+\.shtml(?:$|\?)",
    )
    excluded_patterns = (r"/video/", r"/zt_d/", r"javascript:")
