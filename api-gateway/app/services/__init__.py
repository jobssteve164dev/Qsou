"""
服务层模块
管理外部服务连接和业务逻辑
"""

__all__ = [
    "ElasticsearchService",
    "QdrantService",
    "SearchService",
]


def __getattr__(name):
    """按需加载派生服务，基线模式不承担其依赖成本。"""
    if name == "ElasticsearchService":
        from .elasticsearch_service import ElasticsearchService
        return ElasticsearchService
    if name == "QdrantService":
        from .qdrant_service import QdrantService
        return QdrantService
    if name == "SearchService":
        from .search_service import SearchService
        return SearchService
    raise AttributeError(name)
