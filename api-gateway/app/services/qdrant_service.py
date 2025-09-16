"""
Qdrant向量数据库服务管理器
负责向量存储、语义搜索和相似度计算
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class QdrantService:
    """Qdrant向量数据库服务管理器"""
    
    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self.is_connected = False
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        
    async def connect(self) -> bool:
        """连接到Qdrant"""
        try:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=30
            )
            
            # 测试连接
            collections = self.client.get_collections()
            self.is_connected = True
            
            logger.info(
                "Qdrant连接成功",
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                collections_count=len(collections.collections)
            )
            
            # 确保集合存在
            await self._ensure_collection_exists()
            
            return True
            
        except Exception as e:
            logger.error("Qdrant连接失败", error=str(e))
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """断开Qdrant连接"""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("Qdrant连接已断开")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if not self.client or not self.is_connected:
            return {"status": "disconnected", "error": "No connection"}
        
        try:
            collections = self.client.get_collections()
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "status": "connected",
                "collections_count": len(collections.collections),
                "collection_name": self.collection_name,
                "vectors_count": collection_info.vectors_count,
                "points_count": collection_info.points_count
            }
        except Exception as e:
            logger.error("Qdrant健康检查失败", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def semantic_search(
        self,
        query_vector: List[float],
        filters: Optional[Dict] = None,
        limit: int = 20,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """执行语义搜索"""
        if not self.client or not self.is_connected:
            raise ConnectionError("Qdrant未连接")
        
        try:
            # 观测优先：在真正请求Qdrant前先校验维度是否匹配
            expected_dim = settings.EMBEDDING_DIMENSION
            actual_dim = len(query_vector)
            if actual_dim != expected_dim:
                logger.error(
                    "查询向量维度与集合配置不一致",
                    expected_dim=expected_dim,
                    actual_dim=actual_dim,
                    collection=self.collection_name
                )
                # 主动暴露更明确的错误，便于前端提示与日志排查
                raise ValueError(
                    f"Vector dimension mismatch: expected {expected_dim}, got {actual_dim}. "
                    f"请确保向量模型与Qdrant集合维度一致(集合: {self.collection_name})."
                )
            
            start_time = datetime.now()
            
            # 构建过滤器
            search_filter = self._build_search_filter(filters) if filters else None
            
            # 执行向量搜索
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            search_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # 解析搜索结果
            results = self._parse_search_results(search_result)
            
            logger.info(
                "Qdrant语义搜索完成",
                results_count=len(results),
                search_time_ms=search_time,
                score_threshold=score_threshold
            )
            
            return results
            
        except Exception as e:
            logger.error("Qdrant语义搜索失败", error=str(e))
            raise
    
    async def find_similar_documents(
        self,
        document_id: str,
        limit: int = 10,
        score_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """查找相似文档"""
        if not self.client or not self.is_connected:
            raise ConnectionError("Qdrant未连接")
        
        try:
            # 获取文档向量
            point = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[document_id],
                with_vectors=True
            )
            
            if not point:
                raise ValueError(f"文档 {document_id} 不存在")
            
            document_vector = point[0].vector
            
            # 搜索相似文档（排除自身）
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=document_vector,
                limit=limit + 1,  # +1 因为会包含自身
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # 过滤掉自身
            results = []
            for scored_point in search_result:
                if str(scored_point.id) != document_id:
                    results.append({
                        "id": str(scored_point.id),
                        "score": scored_point.score,
                        "payload": scored_point.payload
                    })
            
            return results[:limit]
            
        except Exception as e:
            logger.error("查找相似文档失败", document_id=document_id, error=str(e))
            raise
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> bool:
        """批量添加文档向量"""
        if not self.client or not self.is_connected:
            raise ConnectionError("Qdrant未连接")
        
        try:
            points = []
            for doc in documents:
                if 'id' not in doc or 'vector' not in doc:
                    logger.warning("文档缺少必要字段", doc_keys=list(doc.keys()))
                    continue
                
                point = models.PointStruct(
                    id=doc['id'],
                    vector=doc['vector'],
                    payload={
                        key: value for key, value in doc.items() 
                        if key not in ['id', 'vector']
                    }
                )
                points.append(point)
            
            if not points:
                logger.warning("没有有效的文档可添加")
                return False
            
            # 批量插入
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(
                "批量添加文档向量完成",
                documents_count=len(points),
                operation_id=operation_info.operation_id
            )
            
            return True
            
        except Exception as e:
            logger.error("批量添加文档向量失败", error=str(e))
            raise
    
    async def delete_document(self, document_id: str) -> bool:
        """删除文档向量"""
        if not self.client or not self.is_connected:
            raise ConnectionError("Qdrant未连接")
        
        try:
            operation_info = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[document_id]
                )
            )
            
            logger.info(
                "删除文档向量完成",
                document_id=document_id,
                operation_id=operation_info.operation_id
            )
            
            return True
            
        except Exception as e:
            logger.error("删除文档向量失败", document_id=document_id, error=str(e))
            return False
    
    def _build_search_filter(self, filters: Dict) -> models.Filter:
        """构建Qdrant搜索过滤器"""
        must_conditions = []
        
        if "source" in filters:
            must_conditions.append(
                models.FieldCondition(
                    key="source",
                    match=models.MatchValue(value=filters["source"])
                )
            )
        
        if "tags" in filters:
            must_conditions.append(
                models.FieldCondition(
                    key="tags",
                    match=models.MatchAny(any=filters["tags"])
                )
            )
        
        if "date_range" in filters:
            date_range = filters["date_range"]
            if "start" in date_range:
                must_conditions.append(
                    models.FieldCondition(
                        key="published_at",
                        range=models.Range(gte=date_range["start"])
                    )
                )
            if "end" in date_range:
                must_conditions.append(
                    models.FieldCondition(
                        key="published_at",
                        range=models.Range(lte=date_range["end"])
                    )
                )
        
        return models.Filter(must=must_conditions) if must_conditions else None
    
    def _parse_search_results(self, search_result) -> List[Dict[str, Any]]:
        """解析Qdrant搜索结果"""
        results = []
        
        for scored_point in search_result:
            payload = scored_point.payload or {}
            
            result = {
                "id": str(scored_point.id),
                "title": payload.get("title", ""),
                "content": payload.get("content", "")[:500] + "..." if len(payload.get("content", "")) > 500 else payload.get("content", ""),
                "source": payload.get("source", ""),
                "url": payload.get("url"),
                "published_at": payload.get("published_at"),
                "relevance_score": float(scored_point.score),
                "tags": payload.get("tags", [])
            }
            
            results.append(result)
        
        return results
    
    async def _ensure_collection_exists(self):
        """确保向量集合存在"""
        try:
            # 检查集合是否存在
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                # 创建集合
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=settings.EMBEDDING_DIMENSION,  # 向量维度
                        distance=models.Distance.COSINE     # 余弦相似度
                    ),
                    optimizers_config=models.OptimizersConfigDiff(
                        default_segment_number=2,
                        max_segment_size=20000
                    ),
                    hnsw_config=models.HnswConfigDiff(
                        m=16,
                        ef_construct=100,
                        full_scan_threshold=10000
                    )
                )
                
                logger.info(f"创建Qdrant集合: {self.collection_name}")
                
        except Exception as e:
            logger.error("创建Qdrant集合失败", error=str(e))
            raise


# 全局Qdrant服务实例
qdrant_service = QdrantService()
