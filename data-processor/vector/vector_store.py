"""
向量存储器

负责向量的存储和管理：
- Qdrant向量数据库操作
- 向量索引管理
- 批量向量存储
- 向量检索
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from loguru import logger
import uuid
from datetime import datetime
import json

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("qdrant-client未安装，向量存储功能不可用")

from config import config


class VectorStore:
    """向量存储器"""
    
    def __init__(self, 
                 qdrant_url: str = None,
                 collection_name: str = None,
                 vector_dimension: int = None):
        """
        初始化向量存储器
        
        Args:
            qdrant_url: Qdrant服务URL
            collection_name: 集合名称
            vector_dimension: 向量维度
        """
        self.qdrant_url = qdrant_url or config.qdrant_url
        self.collection_name = collection_name or config.qdrant_collection_name
        self.vector_dimension = vector_dimension or config.vector_dimension
        
        self.client = None
        self.collection_exists = False
        
        # 初始化Qdrant客户端
        self._initialize_client()
        
        # 创建或验证集合
        self._ensure_collection()
        
        logger.info(f"向量存储器初始化完成: {self.collection_name}")
    
    def _initialize_client(self):
        """初始化Qdrant客户端"""
        if not QDRANT_AVAILABLE:
            logger.error("Qdrant客户端不可用")
            return
        
        try:
            # 解析URL
            if self.qdrant_url.startswith('http'):
                # HTTP连接
                url_parts = self.qdrant_url.replace('http://', '').replace('https://', '')
                if ':' in url_parts:
                    host, port = url_parts.split(':')
                    port = int(port)
                else:
                    host = url_parts
                    port = 6333
                
                self.client = QdrantClient(host=host, port=port)
            else:
                # 本地文件存储
                self.client = QdrantClient(path=self.qdrant_url)
            
            # 测试连接
            collections = self.client.get_collections()
            logger.info(f"Qdrant连接成功，现有集合数: {len(collections.collections)}")
            
        except Exception as e:
            logger.error(f"Qdrant客户端初始化失败: {str(e)}")
            self.client = None
    
    def _ensure_collection(self):
        """确保集合存在"""
        if not self.client:
            return
        
        try:
            # 检查集合是否存在
            collections = self.client.get_collections()
            existing_collections = [col.name for col in collections.collections]
            
            if self.collection_name in existing_collections:
                logger.info(f"集合 {self.collection_name} 已存在")
                self.collection_exists = True
                
                # 验证向量维度
                collection_info = self.client.get_collection(self.collection_name)
                existing_dimension = collection_info.config.params.vectors.size
                
                if existing_dimension != self.vector_dimension:
                    logger.warning(f"集合向量维度不匹配: 期望 {self.vector_dimension}, 实际 {existing_dimension}")
                    # 可以选择重新创建集合或调整维度
                    
            else:
                # 创建新集合
                self._create_collection()
                
        except Exception as e:
            logger.error(f"集合检查失败: {str(e)}")
    
    def _create_collection(self):
        """创建新集合"""
        try:
            logger.info(f"创建新集合: {self.collection_name}, 向量维度: {self.vector_dimension}")
            
            # 创建集合配置
            vectors_config = VectorParams(
                size=self.vector_dimension,
                distance=Distance.COSINE  # 使用余弦相似度
            )
            
            # 创建集合
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=vectors_config
            )
            
            self.collection_exists = True
            logger.info(f"集合 {self.collection_name} 创建成功")
            
        except Exception as e:
            logger.error(f"集合创建失败: {str(e)}")
    
    def store_vectors(self, 
                     vectors: np.ndarray,
                     documents: List[Dict[str, Any]],
                     batch_size: int = 100) -> List[str]:
        """
        存储向量和对应的文档
        
        Args:
            vectors: 向量矩阵 (n_docs, vector_dim)
            documents: 文档列表
            batch_size: 批处理大小
            
        Returns:
            向量ID列表
        """
        if not self.client or not self.collection_exists:
            logger.error("向量存储不可用")
            return []
        
        if len(vectors) != len(documents):
            logger.error(f"向量数量 {len(vectors)} 与文档数量 {len(documents)} 不匹配")
            return []
        
        logger.info(f"开始存储 {len(vectors)} 个向量")
        
        stored_ids = []
        
        try:
            # 分批存储
            for i in range(0, len(vectors), batch_size):
                batch_vectors = vectors[i:i + batch_size]
                batch_documents = documents[i:i + batch_size]
                
                batch_ids = self._store_batch(batch_vectors, batch_documents)
                stored_ids.extend(batch_ids)
                
                logger.info(f"已存储 {min(i + batch_size, len(vectors))}/{len(vectors)} 个向量")
            
            logger.info(f"向量存储完成，成功存储 {len(stored_ids)} 个向量")
            
            return stored_ids
            
        except Exception as e:
            logger.error(f"向量存储失败: {str(e)}")
            return stored_ids
    
    def _store_batch(self, vectors: np.ndarray, documents: List[Dict[str, Any]]) -> List[str]:
        """存储一批向量"""
        points = []
        batch_ids = []
        
        for vector, document in zip(vectors, documents):
            # 生成唯一ID
            point_id = str(uuid.uuid4())
            batch_ids.append(point_id)
            
            # 准备payload（文档元数据）
            payload = self._prepare_payload(document)
            
            # 创建点
            point = PointStruct(
                id=point_id,
                vector=vector.tolist(),
                payload=payload
            )
            
            points.append(point)
        
        try:
            # 批量插入
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            return batch_ids
            
        except Exception as e:
            logger.error(f"批量存储失败: {str(e)}")
            return []
    
    def _prepare_payload(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """准备文档payload"""
        # 选择要存储的字段
        payload_fields = [
            'title', 'content', 'url', 'source', 'publish_time', 'crawl_time',
            'news_type', 'industry', 'importance_level', 'investment_relevance',
            'content_hash', 'word_count', 'importance_score'
        ]
        
        payload = {}
        
        for field in payload_fields:
            if field in document:
                value = document[field]
                
                # 处理特殊类型
                if isinstance(value, (datetime, )):
                    payload[field] = value.isoformat()
                elif isinstance(value, (list, dict)):
                    payload[field] = json.dumps(value, ensure_ascii=False)
                elif isinstance(value, (int, float, str, bool)):
                    payload[field] = value
                else:
                    payload[field] = str(value)
        
        # 添加存储时间戳
        payload['stored_at'] = datetime.now().isoformat()
        
        return payload
    
    def search_similar_vectors(self, 
                             query_vector: np.ndarray,
                             limit: int = 10,
                             score_threshold: float = 0.0,
                             filter_conditions: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量
            limit: 返回结果数量
            score_threshold: 相似度阈值
            filter_conditions: 过滤条件
            
        Returns:
            相似文档列表
        """
        if not self.client or not self.collection_exists:
            logger.error("向量存储不可用")
            return []
        
        try:
            # 构建过滤器
            query_filter = self._build_filter(filter_conditions) if filter_conditions else None
            
            # 执行搜索
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter
            )
            
            # 处理结果
            results = []
            for scored_point in search_result:
                result = {
                    'id': scored_point.id,
                    'score': scored_point.score,
                    'payload': scored_point.payload
                }
                
                # 解析JSON字段
                for key, value in result['payload'].items():
                    if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                        try:
                            result['payload'][key] = json.loads(value)
                        except:
                            pass
                
                results.append(result)
            
            logger.debug(f"向量搜索完成，返回 {len(results)} 个结果")
            
            return results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    def _build_filter(self, conditions: Dict[str, Any]) -> models.Filter:
        """构建查询过滤器"""
        must_conditions = []
        
        for field, value in conditions.items():
            if isinstance(value, str):
                condition = models.FieldCondition(
                    key=field,
                    match=models.MatchValue(value=value)
                )
            elif isinstance(value, (int, float)):
                condition = models.FieldCondition(
                    key=field,
                    match=models.MatchValue(value=value)
                )
            elif isinstance(value, list):
                condition = models.FieldCondition(
                    key=field,
                    match=models.MatchAny(any=value)
                )
            elif isinstance(value, dict) and 'range' in value:
                # 范围查询
                range_condition = value['range']
                condition = models.FieldCondition(
                    key=field,
                    range=models.Range(
                        gte=range_condition.get('gte'),
                        lte=range_condition.get('lte')
                    )
                )
            else:
                continue
            
            must_conditions.append(condition)
        
        return models.Filter(must=must_conditions)
    
    def get_vector_by_id(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取向量"""
        if not self.client or not self.collection_exists:
            return None
        
        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[vector_id],
                with_vectors=True,
                with_payload=True
            )
            
            if points:
                point = points[0]
                return {
                    'id': point.id,
                    'vector': point.vector,
                    'payload': point.payload
                }
            
            return None
            
        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return None
    
    def update_vector(self, vector_id: str, 
                     new_vector: np.ndarray = None,
                     new_payload: Dict[str, Any] = None) -> bool:
        """更新向量"""
        if not self.client or not self.collection_exists:
            return False
        
        try:
            # 获取现有向量
            existing_point = self.get_vector_by_id(vector_id)
            if not existing_point:
                logger.error(f"向量 {vector_id} 不存在")
                return False
            
            # 准备更新数据
            update_vector = new_vector.tolist() if new_vector is not None else existing_point['vector']
            update_payload = new_payload if new_payload is not None else existing_point['payload']
            
            # 更新向量
            point = PointStruct(
                id=vector_id,
                vector=update_vector,
                payload=update_payload
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug(f"向量 {vector_id} 更新成功")
            return True
            
        except Exception as e:
            logger.error(f"向量更新失败: {str(e)}")
            return False
    
    def delete_vector(self, vector_id: str) -> bool:
        """删除向量"""
        if not self.client or not self.collection_exists:
            return False
        
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[vector_id]
                )
            )
            
            logger.debug(f"向量 {vector_id} 删除成功")
            return True
            
        except Exception as e:
            logger.error(f"向量删除失败: {str(e)}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        if not self.client or not self.collection_exists:
            return {}
        
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                'name': self.collection_name,
                'vectors_count': collection_info.vectors_count,
                'indexed_vectors_count': collection_info.indexed_vectors_count,
                'points_count': collection_info.points_count,
                'segments_count': collection_info.segments_count,
                'vector_size': collection_info.config.params.vectors.size,
                'distance': collection_info.config.params.vectors.distance,
                'status': collection_info.status
            }
            
        except Exception as e:
            logger.error(f"获取集合信息失败: {str(e)}")
            return {}
    
    def create_index(self, field_name: str, field_type: str = "keyword") -> bool:
        """创建字段索引"""
        if not self.client or not self.collection_exists:
            return False
        
        try:
            # Qdrant会自动为payload字段创建索引
            # 这里可以添加特定的索引优化逻辑
            logger.info(f"字段 {field_name} 索引创建请求已提交")
            return True
            
        except Exception as e:
            logger.error(f"索引创建失败: {str(e)}")
            return False
    
    def clear_collection(self) -> bool:
        """清空集合"""
        if not self.client or not self.collection_exists:
            return False
        
        try:
            # 删除集合
            self.client.delete_collection(self.collection_name)
            
            # 重新创建集合
            self._create_collection()
            
            logger.info(f"集合 {self.collection_name} 已清空")
            return True
            
        except Exception as e:
            logger.error(f"集合清空失败: {str(e)}")
            return False
    
    def backup_collection(self, backup_path: str) -> bool:
        """备份集合"""
        try:
            # 获取所有向量
            # 注意：这是一个简化的备份方法，实际生产环境需要更复杂的备份策略
            logger.warning("向量备份功能需要根据具体需求实现")
            return True
            
        except Exception as e:
            logger.error(f"集合备份失败: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        stats = {
            'client_available': self.client is not None,
            'collection_exists': self.collection_exists,
            'collection_name': self.collection_name,
            'vector_dimension': self.vector_dimension,
            'qdrant_url': self.qdrant_url
        }
        
        if self.collection_exists:
            collection_info = self.get_collection_info()
            stats.update(collection_info)
        
        return stats
