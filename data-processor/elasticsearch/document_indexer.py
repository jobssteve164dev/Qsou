"""
文档索引器

负责：
- 文档批量索引
- 文档更新和删除
- 索引性能优化
- 错误处理和重试
"""
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from datetime import datetime
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk, parallel_bulk
    from elasticsearch.exceptions import RequestError, ConflictError, NotFoundError
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False
    logger.warning("elasticsearch未安装，文档索引功能不可用")

from ..config import config


class DocumentIndexer:
    """文档索引器"""
    
    def __init__(self, 
                 es_client: Elasticsearch = None,
                 default_index: str = None):
        """
        初始化文档索引器
        
        Args:
            es_client: Elasticsearch客户端
            default_index: 默认索引名称
        """
        self.client = es_client
        self.default_index = default_index or config.es_news_index
        
        # 索引配置
        self.batch_size = config.batch_size
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # 统计信息
        self.stats = {
            'documents_indexed': 0,
            'documents_updated': 0,
            'documents_deleted': 0,
            'indexing_errors': 0,
            'total_indexing_time': 0.0
        }
        
        logger.info("文档索引器初始化完成")
    
    def index_documents(self, 
                       documents: List[Dict[str, Any]],
                       index_name: str = None,
                       batch_size: int = None,
                       parallel: bool = False) -> Dict[str, Any]:
        """
        批量索引文档
        
        Args:
            documents: 文档列表
            index_name: 索引名称
            batch_size: 批处理大小
            parallel: 是否并行处理
            
        Returns:
            索引结果
        """
        if not self.client:
            logger.error("Elasticsearch客户端不可用")
            return self._create_error_result("客户端不可用")
        
        if not documents:
            logger.warning("文档列表为空")
            return self._create_empty_result()
        
        start_time = time.time()
        index_name = index_name or self.default_index
        batch_size = batch_size or self.batch_size
        
        logger.info(f"开始索引 {len(documents)} 个文档到索引 {index_name}")
        
        try:
            # 预处理文档
            processed_documents = self._preprocess_documents(documents, index_name)
            
            # 执行批量索引
            if parallel and len(processed_documents) > batch_size * 2:
                result = self._parallel_bulk_index(processed_documents, batch_size)
            else:
                result = self._bulk_index(processed_documents, batch_size)
            
            # 更新统计信息
            end_time = time.time()
            indexing_time = end_time - start_time
            
            self.stats['documents_indexed'] += result['success_count']
            self.stats['indexing_errors'] += result['error_count']
            self.stats['total_indexing_time'] += indexing_time
            
            result['indexing_time'] = indexing_time
            result['documents_per_second'] = len(documents) / indexing_time if indexing_time > 0 else 0
            
            logger.info(f"文档索引完成，成功: {result['success_count']}, 失败: {result['error_count']}, 耗时: {indexing_time:.2f}秒")
            
            return result
            
        except Exception as e:
            logger.error(f"文档索引失败: {str(e)}")
            return self._create_error_result(str(e))
    
    def _preprocess_documents(self, 
                            documents: List[Dict[str, Any]], 
                            index_name: str) -> List[Dict[str, Any]]:
        """预处理文档"""
        processed_docs = []
        
        for doc in documents:
            try:
                # 复制文档
                processed_doc = doc.copy()
                
                # 添加索引时间
                processed_doc['index_time'] = datetime.now()
                
                # 生成文档ID（如果没有）
                if '_id' not in processed_doc:
                    doc_id = self._generate_document_id(processed_doc)
                    processed_doc['_id'] = doc_id
                
                # 准备Elasticsearch文档格式
                es_doc = {
                    '_index': index_name,
                    '_id': processed_doc.pop('_id'),
                    '_source': processed_doc
                }
                
                processed_docs.append(es_doc)
                
            except Exception as e:
                logger.error(f"文档预处理失败: {str(e)}")
                continue
        
        logger.info(f"文档预处理完成，有效文档: {len(processed_docs)}/{len(documents)}")
        
        return processed_docs
    
    def _generate_document_id(self, document: Dict[str, Any]) -> str:
        """生成文档ID"""
        # 使用内容哈希作为ID
        content_hash = document.get('content_hash')
        if content_hash:
            return content_hash
        
        # 如果没有哈希，使用URL或标题+时间生成
        url = document.get('url', '')
        title = document.get('title', '')
        publish_time = document.get('publish_time', '')
        
        id_string = f"{url}|{title}|{publish_time}"
        return hashlib.md5(id_string.encode('utf-8')).hexdigest()
    
    def _bulk_index(self, documents: List[Dict[str, Any]], batch_size: int) -> Dict[str, Any]:
        """批量索引文档"""
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            # 使用elasticsearch-py的bulk helper
            for success, info in bulk(
                self.client,
                documents,
                chunk_size=batch_size,
                max_retries=self.max_retries,
                initial_backoff=self.retry_delay,
                max_backoff=60
            ):
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(info)
                    logger.error(f"文档索引失败: {info}")
            
            return {
                'success': True,
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"批量索引失败: {str(e)}")
            return {
                'success': False,
                'success_count': success_count,
                'error_count': len(documents) - success_count,
                'errors': [str(e)]
            }
    
    def _parallel_bulk_index(self, documents: List[Dict[str, Any]], batch_size: int) -> Dict[str, Any]:
        """并行批量索引文档"""
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            # 使用parallel_bulk进行并行处理
            for success, info in parallel_bulk(
                self.client,
                documents,
                chunk_size=batch_size,
                thread_count=4,
                max_retries=self.max_retries
            ):
                if success:
                    success_count += len(info)
                else:
                    error_count += len(info)
                    errors.extend(info)
            
            return {
                'success': True,
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"并行批量索引失败: {str(e)}")
            return {
                'success': False,
                'success_count': success_count,
                'error_count': len(documents) - success_count,
                'errors': [str(e)]
            }
    
    def update_document(self, 
                       document_id: str,
                       document: Dict[str, Any],
                       index_name: str = None,
                       upsert: bool = True) -> bool:
        """
        更新单个文档
        
        Args:
            document_id: 文档ID
            document: 文档内容
            index_name: 索引名称
            upsert: 如果文档不存在是否创建
            
        Returns:
            更新是否成功
        """
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        
        try:
            # 添加更新时间
            document['update_time'] = datetime.now()
            
            # 执行更新
            response = self.client.update(
                index=index_name,
                id=document_id,
                body={
                    'doc': document,
                    'doc_as_upsert': upsert
                }
            )
            
            self.stats['documents_updated'] += 1
            
            logger.debug(f"文档更新成功: {document_id}, 结果: {response['result']}")
            return True
            
        except NotFoundError:
            if upsert:
                # 如果文档不存在且允许upsert，尝试创建
                return self.index_document(document, document_id, index_name)
            else:
                logger.error(f"文档不存在: {document_id}")
                return False
        except Exception as e:
            logger.error(f"文档更新失败: {str(e)}")
            return False
    
    def index_document(self, 
                      document: Dict[str, Any],
                      document_id: str = None,
                      index_name: str = None) -> bool:
        """
        索引单个文档
        
        Args:
            document: 文档内容
            document_id: 文档ID
            index_name: 索引名称
            
        Returns:
            索引是否成功
        """
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        document_id = document_id or self._generate_document_id(document)
        
        try:
            # 添加索引时间
            document['index_time'] = datetime.now()
            
            # 执行索引
            response = self.client.index(
                index=index_name,
                id=document_id,
                body=document
            )
            
            self.stats['documents_indexed'] += 1
            
            logger.debug(f"文档索引成功: {document_id}, 结果: {response['result']}")
            return True
            
        except Exception as e:
            logger.error(f"文档索引失败: {str(e)}")
            self.stats['indexing_errors'] += 1
            return False
    
    def delete_document(self, 
                       document_id: str,
                       index_name: str = None) -> bool:
        """
        删除文档
        
        Args:
            document_id: 文档ID
            index_name: 索引名称
            
        Returns:
            删除是否成功
        """
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        
        try:
            response = self.client.delete(
                index=index_name,
                id=document_id
            )
            
            self.stats['documents_deleted'] += 1
            
            logger.debug(f"文档删除成功: {document_id}, 结果: {response['result']}")
            return True
            
        except NotFoundError:
            logger.warning(f"文档不存在: {document_id}")
            return False
        except Exception as e:
            logger.error(f"文档删除失败: {str(e)}")
            return False
    
    def delete_by_query(self, 
                       query: Dict[str, Any],
                       index_name: str = None) -> Dict[str, Any]:
        """
        根据查询删除文档
        
        Args:
            query: 删除查询
            index_name: 索引名称
            
        Returns:
            删除结果
        """
        if not self.client:
            return {'deleted': 0, 'error': '客户端不可用'}
        
        index_name = index_name or self.default_index
        
        try:
            response = self.client.delete_by_query(
                index=index_name,
                body={'query': query}
            )
            
            deleted_count = response.get('deleted', 0)
            self.stats['documents_deleted'] += deleted_count
            
            logger.info(f"批量删除完成，删除文档数: {deleted_count}")
            
            return {
                'deleted': deleted_count,
                'took': response.get('took', 0),
                'timed_out': response.get('timed_out', False)
            }
            
        except Exception as e:
            logger.error(f"批量删除失败: {str(e)}")
            return {'deleted': 0, 'error': str(e)}
    
    def get_document(self, 
                    document_id: str,
                    index_name: str = None) -> Optional[Dict[str, Any]]:
        """获取文档"""
        if not self.client:
            return None
        
        index_name = index_name or self.default_index
        
        try:
            response = self.client.get(
                index=index_name,
                id=document_id
            )
            
            return response['_source']
            
        except NotFoundError:
            logger.warning(f"文档不存在: {document_id}")
            return None
        except Exception as e:
            logger.error(f"获取文档失败: {str(e)}")
            return None
    
    def exists_document(self, 
                       document_id: str,
                       index_name: str = None) -> bool:
        """检查文档是否存在"""
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        
        try:
            return self.client.exists(
                index=index_name,
                id=document_id
            )
            
        except Exception as e:
            logger.error(f"检查文档存在性失败: {str(e)}")
            return False
    
    def refresh_index(self, index_name: str = None) -> bool:
        """刷新索引"""
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        
        try:
            self.client.indices.refresh(index=index_name)
            logger.debug(f"索引刷新成功: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"索引刷新失败: {str(e)}")
            return False
    
    def get_document_count(self, 
                          index_name: str = None,
                          query: Dict[str, Any] = None) -> int:
        """获取文档数量"""
        if not self.client:
            return 0
        
        index_name = index_name or self.default_index
        
        try:
            body = {'query': query} if query else None
            
            response = self.client.count(
                index=index_name,
                body=body
            )
            
            return response['count']
            
        except Exception as e:
            logger.error(f"获取文档数量失败: {str(e)}")
            return 0
    
    def optimize_indexing_performance(self, index_name: str = None) -> bool:
        """优化索引性能"""
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        
        try:
            # 临时禁用刷新
            self.client.indices.put_settings(
                index=index_name,
                body={
                    "refresh_interval": "-1",
                    "number_of_replicas": 0
                }
            )
            
            logger.info(f"索引 {index_name} 性能优化设置已应用")
            return True
            
        except Exception as e:
            logger.error(f"索引性能优化失败: {str(e)}")
            return False
    
    def restore_indexing_settings(self, index_name: str = None) -> bool:
        """恢复索引设置"""
        if not self.client:
            return False
        
        index_name = index_name or self.default_index
        
        try:
            # 恢复正常设置
            self.client.indices.put_settings(
                index=index_name,
                body={
                    "refresh_interval": "1s",
                    "number_of_replicas": 0
                }
            )
            
            # 强制刷新
            self.client.indices.refresh(index=index_name)
            
            logger.info(f"索引 {index_name} 设置已恢复")
            return True
            
        except Exception as e:
            logger.error(f"索引设置恢复失败: {str(e)}")
            return False
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """创建空结果"""
        return {
            'success': True,
            'success_count': 0,
            'error_count': 0,
            'errors': [],
            'indexing_time': 0.0,
            'documents_per_second': 0.0
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            'success': False,
            'success_count': 0,
            'error_count': 1,
            'errors': [error_message],
            'indexing_time': 0.0,
            'documents_per_second': 0.0
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 计算平均索引时间
        if stats['documents_indexed'] > 0:
            stats['avg_indexing_time'] = stats['total_indexing_time'] / stats['documents_indexed']
        else:
            stats['avg_indexing_time'] = 0.0
        
        return stats
    
    def reset_statistics(self):
        """重置统计信息"""
        for key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] = 0
