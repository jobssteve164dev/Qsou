from .base import NewsHTMLAdapter


class NeteaseFinanceAdapter(NewsHTMLAdapter):
    source_id = "netease-finance"
    adapter_id = "netease-finance-news"
    version = "1.1.0"
    content_container_patterns = (r"\bpost_body\b",)
    link_patterns = (
        r"money\.163\.com/\d{2}/\d{4}/\d{2}/[A-Z0-9]+\.html(?:$|\?)",
        r"money\.163\.com/article/[A-Z0-9]+\.html(?:$|\?)",
        r"www\.163\.com/money/article/[A-Z0-9]+\.html(?:$|\?)",
    )
    excluded_patterns = (r"/special/", r"javascript:")
