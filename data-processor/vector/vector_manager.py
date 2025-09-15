"""
向量管理器

统一管理向量化、存储和搜索功能：
- 文档向量化处理
- 批量向量存储
- 向量索引管理
- 搜索服务接口
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .embeddings import TextEmbedder
from .vector_store import VectorStore
from .similarity_search import SimilaritySearcher
from ..config import config


class VectorManager:
    """向量管理器"""
    
    def __init__(self,
                 embedder_type: str = "sentence_transformers",
                 embedder_model: str = None,
                 qdrant_url: str = None,
                 collection_name: str = None):
        """
        初始化向量管理器
        
        Args:
            embedder_type: 向量化器类型
            embedder_model: 向量化模型名称
            qdrant_url: Qdrant服务URL
            collection_name: 向量集合名称
        """
        # 初始化组件
        self.embedder = TextEmbedder(
            model_type=embedder_type,
            model_name=embedder_model
        )
        
        self.vector_store = VectorStore(
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            vector_dimension=self.embedder.vector_dimension
        )
        
        self.similarity_searcher = SimilaritySearcher(
            embedder=self.embedder,
            vector_store=self.vector_store
        )
        
        # 处理统计
        self.stats = {
            'documents_processed': 0,
            'vectors_stored': 0,
            'searches_performed': 0,
            'total_processing_time': 0.0,
            'last_update': None
        }
        
        # 线程池用于并行处理
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("向量管理器初始化完成")
    
    def process_and_store_documents(self, 
                                  documents: List[Dict[str, Any]],
                                  batch_size: int = None,
                                  update_existing: bool = False) -> Dict[str, Any]:
        """
        处理文档并存储向量
        
        Args:
            documents: 文档列表
            batch_size: 批处理大小
            update_existing: 是否更新已存在的向量
            
        Returns:
            处理结果
        """
        start_time = datetime.now()
        batch_size = batch_size or config.batch_size
        
        logger.info(f"开始处理和存储 {len(documents)} 个文档的向量")
        
        try:
            # 验证文档
            valid_documents = self._validate_documents(documents)
            
            if not valid_documents:
                logger.warning("没有有效的文档需要处理")
                return self._create_empty_result()
            
            # 检查重复文档
            if not update_existing:
                valid_documents = self._filter_existing_documents(valid_documents)
            
            if not valid_documents:
                logger.info("所有文档已存在，跳过处理")
                return self._create_empty_result()
            
            # 分批处理
            all_stored_ids = []
            total_processed = 0
            
            for i in range(0, len(valid_documents), batch_size):
                batch_documents = valid_documents[i:i + batch_size]
                
                # 处理批次
                batch_result = self._process_document_batch(batch_documents)
                
                if batch_result['success']:
                    all_stored_ids.extend(batch_result['stored_ids'])
                    total_processed += len(batch_documents)
                
                logger.info(f"已处理 {min(i + batch_size, len(valid_documents))}/{len(valid_documents)} 个文档")
            
            # 更新统计信息
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            self.stats['documents_processed'] += total_processed
            self.stats['vectors_stored'] += len(all_stored_ids)
            self.stats['total_processing_time'] += processing_time
            self.stats['last_update'] = end_time.isoformat()
            
            result = {
                'success': True,
                'processed_count': total_processed,
                'stored_count': len(all_stored_ids),
                'stored_ids': all_stored_ids,
                'processing_time': processing_time,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            logger.info(f"文档向量处理完成，成功存储 {len(all_stored_ids)} 个向量，耗时 {processing_time:.2f} 秒")
            
            return result
            
        except Exception as e:
            logger.error(f"文档向量处理失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processed_count': 0,
                'stored_count': 0
            }
    
    def _process_document_batch(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理文档批次"""
        try:
            # 提取文本内容
            texts = []
            for doc in documents:
                title = doc.get('title', '')
                content = doc.get('content', '')
                # 合并标题和内容
                full_text = f"{title} {content}".strip()
                texts.append(full_text)
            
            # 批量向量化
            vectors = self.embedder.embed_batch(texts)
            
            if len(vectors) == 0:
                logger.warning("向量化失败，没有生成向量")
                return {'success': False, 'stored_ids': []}
            
            # 存储向量
            stored_ids = self.vector_store.store_vectors(vectors, documents)
            
            return {
                'success': True,
                'stored_ids': stored_ids
            }
            
        except Exception as e:
            logger.error(f"批次处理失败: {str(e)}")
            return {'success': False, 'stored_ids': []}
    
    def search(self,
               query: str,
               search_type: str = "semantic",
               limit: int = 10,
               filters: Dict[str, Any] = None,
               **kwargs) -> List[Dict[str, Any]]:
        """
        执行搜索
        
        Args:
            query: 查询文本
            search_type: 搜索类型 ("semantic", "hybrid", "keyword")
            limit: 返回结果数量
            filters: 过滤条件
            **kwargs: 其他搜索参数
            
        Returns:
            搜索结果列表
        """
        if not query:
            logger.warning("查询为空")
            return []
        
        try:
            self.stats['searches_performed'] += 1
            
            if search_type == "semantic":
                results = self.similarity_searcher.semantic_search(
                    query=query,
                    limit=limit,
                    filters=filters,
                    **kwargs
                )
            elif search_type == "hybrid":
                results = self.similarity_searcher.hybrid_search(
                    query=query,
                    limit=limit,
                    filters=filters,
                    **kwargs
                )
            elif search_type == "multi_query":
                queries = kwargs.get('queries', [query])
                results = self.similarity_searcher.multi_query_search(
                    queries=queries,
                    limit=limit,
                    filters=filters,
                    **kwargs
                )
            else:
                logger.warning(f"不支持的搜索类型: {search_type}")
                results = self.similarity_searcher.semantic_search(
                    query=query,
                    limit=limit,
                    filters=filters
                )
            
            logger.info(f"搜索完成，查询: '{query[:50]}...', 类型: {search_type}, 返回 {len(results)} 个结果")
            
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return []
    
    def find_similar_documents(self,
                             document_id: str,
                             limit: int = 10,
                             filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """查找相似文档"""
        try:
            results = self.similarity_searcher.find_similar_documents(
                document_id=document_id,
                limit=limit,
                filters=filters
            )
            
            self.stats['searches_performed'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"相似文档搜索失败: {str(e)}")
            return []
    
    def update_document_vector(self,
                             document_id: str,
                             document: Dict[str, Any]) -> bool:
        """更新文档向量"""
        try:
            # 生成新向量
            title = document.get('title', '')
            content = document.get('content', '')
            full_text = f"{title} {content}".strip()
            
            new_vector = self.embedder.embed_text(full_text)
            
            # 准备新的payload
            new_payload = self.vector_store._prepare_payload(document)
            
            # 更新向量
            success = self.vector_store.update_vector(
                vector_id=document_id,
                new_vector=new_vector,
                new_payload=new_payload
            )
            
            if success:
                logger.info(f"文档向量更新成功: {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"文档向量更新失败: {str(e)}")
            return False
    
    def delete_document_vector(self, document_id: str) -> bool:
        """删除文档向量"""
        try:
            success = self.vector_store.delete_vector(document_id)
            
            if success:
                logger.info(f"文档向量删除成功: {document_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"文档向量删除失败: {str(e)}")
            return False
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取文档"""
        try:
            return self.vector_store.get_vector_by_id(document_id)
            
        except Exception as e:
            logger.error(f"文档获取失败: {str(e)}")
            return None
    
    def build_index_from_documents(self, 
                                 documents: List[Dict[str, Any]],
                                 clear_existing: bool = False,
                                 batch_size: int = None) -> Dict[str, Any]:
        """从文档构建向量索引"""
        if clear_existing:
            logger.info("清空现有向量集合")
            self.vector_store.clear_collection()
        
        # 处理和存储所有文档
        result = self.process_and_store_documents(
            documents=documents,
            batch_size=batch_size,
            update_existing=True
        )
        
        return result
    
    def _validate_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证文档格式"""
        valid_documents = []
        
        for i, doc in enumerate(documents):
            if not isinstance(doc, dict):
                logger.warning(f"文档 {i} 不是字典类型，跳过")
                continue
            
            # 检查必需字段
            title = doc.get('title', '')
            content = doc.get('content', '')
            
            if not title and not content:
                logger.warning(f"文档 {i} 标题和内容均为空，跳过")
                continue
            
            # 检查内容长度
            full_text = f"{title} {content}".strip()
            if len(full_text) < 10:
                logger.warning(f"文档 {i} 内容过短，跳过")
                continue
            
            valid_documents.append(doc)
        
        logger.info(f"文档验证完成，有效文档: {len(valid_documents)}/{len(documents)}")
        
        return valid_documents
    
    def _filter_existing_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤已存在的文档"""
        # 简化实现：基于content_hash检查
        # 实际实现可能需要更复杂的重复检测逻辑
        
        filtered_documents = []
        
        for doc in documents:
            content_hash = doc.get('content_hash')
            if content_hash:
                # 这里可以实现基于哈希的重复检测
                # 暂时简化处理
                pass
            
            filtered_documents.append(doc)
        
        return filtered_documents
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """创建空结果"""
        return {
            'success': True,
            'processed_count': 0,
            'stored_count': 0,
            'stored_ids': [],
            'processing_time': 0.0,
            'start_time': datetime.now().isoformat(),
            'end_time': datetime.now().isoformat()
        }
    
    async def process_documents_async(self, 
                                    documents: List[Dict[str, Any]],
                                    **kwargs) -> Dict[str, Any]:
        """异步处理文档"""
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            self.executor,
            self.process_and_store_documents,
            documents,
            kwargs.get('batch_size'),
            kwargs.get('update_existing', False)
        )
        
        return result
    
    async def search_async(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """异步搜索"""
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            self.executor,
            self.search,
            query,
            kwargs.get('search_type', 'semantic'),
            kwargs.get('limit', 10),
            kwargs.get('filters'),
            **{k: v for k, v in kwargs.items() if k not in ['search_type', 'limit', 'filters']}
        )
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 添加组件统计
        stats['embedder'] = self.embedder.get_model_info()
        stats['vector_store'] = self.vector_store.get_statistics()
        stats['similarity_searcher'] = self.similarity_searcher.get_search_statistics()
        
        # 计算平均处理时间
        if stats['documents_processed'] > 0:
            stats['avg_processing_time'] = stats['total_processing_time'] / stats['documents_processed']
        else:
            stats['avg_processing_time'] = 0.0
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health_status = {
            'status': 'healthy',
            'components': {},
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # 检查向量化器
            test_vector = self.embedder.embed_text("测试文本")
            health_status['components']['embedder'] = {
                'status': 'healthy' if len(test_vector) > 0 else 'unhealthy',
                'vector_dimension': len(test_vector)
            }
        except Exception as e:
            health_status['components']['embedder'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # 检查向量存储
        try:
            collection_info = self.vector_store.get_collection_info()
            health_status['components']['vector_store'] = {
                'status': 'healthy' if collection_info else 'unhealthy',
                'collection_info': collection_info
            }
        except Exception as e:
            health_status['components']['vector_store'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # 检查搜索器
        try:
            # 简单的搜索测试
            test_results = self.similarity_searcher.semantic_search("测试", limit=1)
            health_status['components']['similarity_searcher'] = {
                'status': 'healthy',
                'test_results_count': len(test_results)
            }
        except Exception as e:
            health_status['components']['similarity_searcher'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # 判断整体状态
        component_statuses = [comp['status'] for comp in health_status['components'].values()]
        if 'unhealthy' in component_statuses:
            health_status['status'] = 'unhealthy'
        elif not component_statuses:
            health_status['status'] = 'unknown'
        
        return health_status
    
    def cleanup(self):
        """清理资源"""
        try:
            # 清理向量化器
            if hasattr(self.embedder, 'cleanup'):
                self.embedder.cleanup()
            
            # 关闭线程池
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
            
            logger.info("向量管理器资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")


# 全局向量管理器实例
vector_manager = VectorManager()
