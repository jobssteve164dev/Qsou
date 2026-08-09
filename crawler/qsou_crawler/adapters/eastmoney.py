from .base import NewsHTMLAdapter


class EastmoneyAdapter(NewsHTMLAdapter):
    source_id = "eastmoney"
    adapter_id = "eastmoney-news"
    version = "1.0.0"
    link_patterns = (
        r"finance\.eastmoney\.com/a/\d+\.html(?:$|\?)",
        r"eastmoney\.com/news/\d+[,\d]*\.html(?:$|\?)",
    )
    excluded_patterns = (r"/video/", r"/zt/", r"javascript:")
