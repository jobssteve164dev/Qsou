from .base import NewsHTMLAdapter


class SohuFinanceAdapter(NewsHTMLAdapter):
    source_id = "sohu-finance"
    adapter_id = "sohu-finance-news"
    version = "1.0.0"
    link_patterns = (
        r"sohu\.com/a/\d+_\d+(?:$|[/?])",
        r"business\.sohu\.com/\d{8}/n\d+\.shtml(?:$|\?)",
    )
    excluded_patterns = (r"/picture/", r"/video/", r"javascript:")
