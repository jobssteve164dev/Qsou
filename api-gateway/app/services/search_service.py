"""
统一搜索服务
整合Elasticsearch全文搜索和Qdrant语义搜索功能
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import structlog

from app.core.config import settings
from qsou_data import DataAssetStore

logger = structlog.get_logger(__name__)


class DisabledDerivedService:
    """基线模式下明确表示派生索引未启用。"""

    is_connected = False
    client = None

    async def connect(self) -> bool:
        return False

    async def disconnect(self):
        return None

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "disabled"}

    async def get_suggestions(self, query: str, size: int = 5) -> List[str]:
        return []

    async def find_similar_documents(self, document_id: str, limit: int = 10):
        raise RuntimeError("派生向量检索未启用")


class SearchService:
    """统一搜索服务管理器"""
    
    def __init__(self):
        if settings.ENABLE_DERIVED_SEARCH:
            from .elasticsearch_service import elasticsearch_service
            from .qdrant_service import qdrant_service
            self.elasticsearch = elasticsearch_service
            self.qdrant = qdrant_service
        else:
            self.elasticsearch = DisabledDerivedService()
            self.qdrant = DisabledDerivedService()
        self.data_assets = DataAssetStore()
        
    async def initialize(self) -> bool:
        """初始化搜索服务"""
        try:
            if not settings.ENABLE_DERIVED_SEARCH:
                self.data_assets.health()
                logger.info("派生搜索未启用，使用自主数据基线检索")
                return True

            # 并行连接两个服务
            es_task = asyncio.create_task(self.elasticsearch.connect())
            qdrant_task = asyncio.create_task(self.qdrant.connect())
            
            es_connected, qdrant_connected = await asyncio.gather(es_task, qdrant_task)
            
            self.data_assets.health()
            logger.info(
                "搜索服务初始化完成",
                elasticsearch_connected=es_connected,
                qdrant_connected=qdrant_connected,
                local_data_ready=True,
            )
            return True
                
        except Exception as e:
            logger.error("搜索服务初始化异常", error=str(e))
            return False
    
    async def shutdown(self):
        """关闭搜索服务"""
        await asyncio.gather(
            self.elasticsearch.disconnect(),
            self.qdrant.disconnect()
        )
        logger.info("搜索服务已关闭")
    
    async def health_check(self) -> Dict[str, Any]:
        """搜索服务健康检查"""
        try:
            if settings.ENABLE_DERIVED_SEARCH:
                es_task = asyncio.create_task(self.elasticsearch.health_check())
                qdrant_task = asyncio.create_task(self.qdrant.health_check())
                es_health, qdrant_health = await asyncio.gather(es_task, qdrant_task)
            else:
                es_health = {"status": "disabled"}
                qdrant_health = {"status": "disabled"}
            
            data_health = self.data_assets.health()
            derived_ready = (
                es_health.get("status") == "connected"
                and qdrant_health.get("status") == "connected"
            )
            
            return {
                "status": "healthy" if data_health.get("status") == "healthy" else "unhealthy",
                "mode": "derived" if derived_ready else "local_baseline",
                "data_assets": data_health,
                "elasticsearch": es_health,
                "qdrant": qdrant_health,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("搜索服务健康检查失败", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def search(
        self,
        query: str,
        search_type: str = "hybrid",
        filters: Optional[Dict] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "relevance"
    ) -> Dict[str, Any]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            search_type: 搜索类型 (keyword, semantic, hybrid)
            filters: 搜索过滤器
            page: 页码
            page_size: 每页大小
            sort_by: 排序方式
        """
        start_time = datetime.now()
        
        logger.info(
            "开始执行搜索",
            query=query,
            search_type=search_type,
            page=page,
            page_size=page_size
        )
        
        try:
            if search_type == "keyword":
                result = (
                    await self._keyword_search(query, filters, page, page_size, sort_by)
                    if self.elasticsearch.is_connected
                    else self._local_search(query, filters, page, page_size)
                )
            elif search_type == "semantic":
                result = (
                    await self._semantic_search(query, filters, page, page_size)
                    if self.qdrant.is_connected
                    else self._local_search(query, filters, page, page_size)
                )
            elif search_type == "hybrid":
                result = (
                    await self._hybrid_search(query, filters, page, page_size, sort_by)
                    if self.elasticsearch.is_connected and self.qdrant.is_connected
                    else self._local_search(query, filters, page, page_size)
                )
            else:
                raise ValueError(f"不支持的搜索类型: {search_type}")
            
            total_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result["search_time_ms"] = total_time
            
            logger.info(
                "搜索完成",
                query=query,
                search_type=search_type,
                total_results=result.get("total_count", 0),
                search_time_ms=total_time
            )
            
            return result
            
        except Exception as e:
            logger.warning("派生搜索不可用，改用自有标准文档检索", query=query, error=str(e))
            result = self._local_search(query, filters, page, page_size)
            result["search_time_ms"] = int((datetime.now() - start_time).total_seconds() * 1000)
            result["derived_warning"] = str(e)
            return result

    def _local_search(
        self,
        query: str,
        filters: Optional[Dict],
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        source_id = None
        if filters:
            candidate = filters.get("source_id") or filters.get("source")
            if candidate:
                try:
                    self.data_assets.registry.get(candidate)
                    source_id = candidate
                except ValueError:
                    source_id = None
        result = self.data_assets.search_documents(
            query,
            source_id=source_id,
            page=page,
            page_size=page_size,
        )
        result["search_type"] = "local_baseline"
        result["aggregations"] = {}
        return result
    
    async def get_suggestions(self, query: str, size: int = 5) -> List[str]:
        """仅返回真实派生索引提供的搜索建议。"""
        try:
            suggestions = await self.elasticsearch.get_suggestions(query, size)
            return suggestions[:size]
            
        except Exception as e:
            logger.error("获取搜索建议失败", query=query, error=str(e))
            return []
    
    async def find_similar_documents(
        self,
        document_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """查找相似文档"""
        try:
            similar_docs = await self.qdrant.find_similar_documents(
                document_id=document_id,
                limit=limit,
                score_threshold=0.7
            )
            
            logger.info(
                "查找相似文档完成",
                document_id=document_id,
                similar_count=len(similar_docs)
            )
            
            return similar_docs
            
        except Exception as e:
            logger.error("查找相似文档失败", document_id=document_id, error=str(e))
            raise
    
    async def _keyword_search(
        self,
        query: str,
        filters: Optional[Dict],
        page: int,
        page_size: int,
        sort_by: str
    ) -> Dict[str, Any]:
        """执行关键词搜索"""
        result = await self.elasticsearch.search_documents(
            query=query,
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by
        )
        
        return {
            "total_count": result["total_count"],
            "results": result["results"],
            "search_type": "keyword",
            "aggregations": result.get("aggregations", {})
        }
    
    async def _semantic_search(
        self,
        query: str,
        filters: Optional[Dict],
        page: int,
        page_size: int
    ) -> Dict[str, Any]:
        """执行语义搜索"""
        # 观测优先：在关键节点记录调试信息
        logger.info("开始语义搜索-向量化阶段", query=query[:50])
        query_vector = await self._vectorize_query(query)
        logger.info(
            "语义搜索-向量化完成",
            vector_dim=len(query_vector)
        )
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 执行向量搜索，获取更多结果用于分页
        try:
            all_results = await self.qdrant.semantic_search(
                query_vector=query_vector,
                filters=filters,
                limit=offset + page_size,
                score_threshold=0.3
            )
        except Exception as e:
            # 强化错误上下文，暴露核心线索
            logger.error(
                "语义搜索调用Qdrant失败",
                error=str(e),
                vector_dim=len(query_vector),
                expected_dim=settings.EMBEDDING_DIMENSION,
                page=page,
                page_size=page_size
            )
            raise
        
        # 分页处理
        results = all_results[offset:offset + page_size]
        
        return {
            "total_count": len(all_results),
            "results": results,
            "search_type": "semantic"
        }
    
    async def _hybrid_search(
        self,
        query: str,
        filters: Optional[Dict],
        page: int,
        page_size: int,
        sort_by: str
    ) -> Dict[str, Any]:
        """执行混合搜索（关键词 + 语义）"""
        
        # 并行执行两种搜索
        keyword_task = asyncio.create_task(
            self._keyword_search(query, filters, 1, page_size * 2, sort_by)
        )
        semantic_task = asyncio.create_task(
            self._semantic_search(query, filters, 1, page_size * 2)
        )
        
        keyword_result, semantic_result = await asyncio.gather(keyword_task, semantic_task)
        
        # 合并和重排序结果
        merged_results = self._merge_search_results(
            keyword_result["results"],
            semantic_result["results"],
            page,
            page_size
        )
        
        total_count = max(keyword_result["total_count"], semantic_result["total_count"])
        
        return {
            "total_count": total_count,
            "results": merged_results,
            "search_type": "hybrid",
            "aggregations": keyword_result.get("aggregations", {})
        }
    
    def _merge_search_results(
        self,
        keyword_results: List[Dict],
        semantic_results: List[Dict],
        page: int,
        page_size: int
    ) -> List[Dict[str, Any]]:
        """合并关键词和语义搜索结果"""
        
        # 创建结果字典，避免重复
        merged_dict = {}
        
        # 添加关键词搜索结果（权重0.6）
        for result in keyword_results:
            doc_id = result["id"]
            result["final_score"] = result["relevance_score"] * 0.6
            result["search_sources"] = ["keyword"]
            merged_dict[doc_id] = result
        
        # 添加语义搜索结果（权重0.4）
        for result in semantic_results:
            doc_id = result["id"]
            if doc_id in merged_dict:
                # 如果已存在，合并分数
                merged_dict[doc_id]["final_score"] += result["relevance_score"] * 0.4
                merged_dict[doc_id]["search_sources"].append("semantic")
            else:
                # 新结果
                result["final_score"] = result["relevance_score"] * 0.4
                result["search_sources"] = ["semantic"]
                merged_dict[doc_id] = result
        
        # 按最终分数排序
        sorted_results = sorted(
            merged_dict.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )
        
        # 分页处理
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # 更新relevance_score为最终分数
        for result in sorted_results:
            result["relevance_score"] = result["final_score"]
            del result["final_score"]
        
        return sorted_results[start_idx:end_idx]
    
    async def _vectorize_query(self, query: str) -> List[float]:
        """将查询文本转换为向量"""
        try:
            import sys
            import os
            
            # 添加data-processor路径到Python路径
            data_processor_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data-processor')
            if data_processor_path not in sys.path:
                sys.path.append(data_processor_path)
            
            from vector.embeddings import TextEmbedder
            import numpy as np
            
            # 创建文本向量化器（模型与维度由settings控制）
            embedder = TextEmbedder(
                model_type="sentence_transformers",
                model_name=settings.SENTENCE_TRANSFORMER_MODEL,
                cache_embeddings=True
            )
            
            # 生成向量
            vector = embedder.embed_text(query)
            
            # 转换为Python list
            if isinstance(vector, np.ndarray):
                vector = vector.tolist()
            
            # 如果维度与配置不一致，记录警告并做安全扩展/截断
            dim = len(vector)
            expected = settings.EMBEDDING_DIMENSION
            if dim != expected:
                logger.warning(
                    "向量维度与配置不一致，将进行调整",
                    actual_dim=dim,
                    expected_dim=expected
                )
                if dim > expected:
                    vector = vector[:expected]
                else:
                    vector = vector + [0.0] * (expected - dim)
            
            logger.info("查询向量化完成", query=query[:50], vector_dim=len(vector))
            return vector
            
        except Exception as e:
            logger.error("查询向量化失败", query=query, error=str(e))
            raise RuntimeError("语义向量生成失败") from e


# 全局搜索服务实例
search_service = SearchService()
