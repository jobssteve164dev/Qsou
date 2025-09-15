"""
向量处理模块

包含：
- 文本向量化
- 向量存储
- 相似度搜索
- 向量索引管理
"""

from .embeddings import TextEmbedder
from .vector_store import VectorStore
from .similarity_search import SimilaritySearcher

__all__ = [
    "TextEmbedder",
    "VectorStore",
    "SimilaritySearcher"
]
