from .base import NewsHTMLAdapter


class YicaiAdapter(NewsHTMLAdapter):
    source_id = "yicai"
    adapter_id = "yicai-news"
    version = "1.2.0"
    content_container_patterns = (r"\bm-txt\b",)
    link_patterns = (r"yicai\.com/news/\d+\.html(?:$|\?)",)
    excluded_patterns = (r"/video/", r"javascript:")
