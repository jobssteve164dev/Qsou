"""
增量处理器

负责：
- 增量数据处理
- 增量索引更新
- 处理队列管理
- 错误重试机制
"""
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

from .change_detector import ChangeDetector
from pipeline import DataProcessingPipeline
from vector.vector_manager import VectorManager
from elasticsearch.document_indexer import DocumentIndexer
from config import config


class IncrementalProcessor:
    """增量处理器"""
    
    def __init__(self,
                 change_detector: ChangeDetector = None,
                 data_pipeline: DataProcessingPipeline = None,
                 vector_manager: VectorManager = None,
                 document_indexer: DocumentIndexer = None):
        """
        初始化增量处理器
        
        Args:
            change_detector: 变更检测器
            data_pipeline: 数据处理管道
            vector_manager: 向量管理器
            document_indexer: 文档索引器
        """
        self.change_detector = change_detector or ChangeDetector()
        self.data_pipeline = data_pipeline or DataProcessingPipeline()
        self.vector_manager = vector_manager or VectorManager()
        self.document_indexer = document_indexer or DocumentIndexer()
        
        # 处理配置
        self.batch_size = config.batch_size
        self.max_retries = 3
        self.retry_delay = 5.0
        
        # 处理统计
        self.stats = {
            'total_processed': 0,
            'created_processed': 0,
            'updated_processed': 0,
            'deleted_processed': 0,
            'processing_errors': 0,
            'total_processing_time': 0.0,
            'last_processing_time': None
        }
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("增量处理器初始化完成")
    
    def process_incremental_changes(self, 
                                  new_documents: List[Dict[str, Any]],
                                  time_threshold: Optional[datetime] = None,
                                  enable_full_processing: bool = True) -> Dict[str, Any]:
        """
        处理增量变更
        
        Args:
            new_documents: 新文档列表
            time_threshold: 时间阈值
            enable_full_processing: 是否启用完整处理（NLP、向量化等）
            
        Returns:
            处理结果
        """
        start_time = datetime.now()
        
        logger.info(f"开始增量处理，文档数: {len(new_documents)}")
        
        try:
            # 1. 检测变更
            change_result = self.change_detector.detect_incremental_changes(
                new_documents, time_threshold
            )
            
            changes = change_result['changes']
            
            # 2. 处理各种类型的变更
            processing_results = {
                'created': self._process_created_documents(
                    changes['created'], enable_full_processing
                ),
                'updated': self._process_updated_documents(
                    changes['updated'], enable_full_processing
                ),
                'deleted': self._process_deleted_documents(
                    changes['deleted']
                )
            }
            
            # 3. 更新统计信息
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            self._update_statistics(processing_results, processing_time)
            
            # 4. 生成处理报告
            result = {
                'success': True,
                'processing_time': processing_time,
                'change_detection': change_result,
                'processing_results': processing_results,
                'summary': self._generate_processing_summary(processing_results),
                'timestamp': end_time.isoformat()
            }
            
            logger.info(f"增量处理完成，耗时: {processing_time:.2f}秒")
            logger.info(f"处理摘要: {result['summary']}")
            
            return result
            
        except Exception as e:
            logger.error(f"增量处理失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
    
    def _process_created_documents(self, 
                                 created_changes: List[Dict[str, Any]],
                                 enable_full_processing: bool) -> Dict[str, Any]:
        """处理新增文档"""
        if not created_changes:
            return {'success': True, 'processed_count': 0, 'errors': []}
        
        logger.info(f"处理 {len(created_changes)} 个新增文档")
        
        # 提取文档数据
        documents = []
        for change in created_changes:
            # 这里需要从变更记录中重构完整的文档数据
            # 实际实现中，可能需要从原始数据源重新获取完整文档
            doc_id = change['id']
            # 简化处理：假设我们有完整的文档数据
            # 实际应用中需要根据ID获取完整文档
            documents.append({
                'id': doc_id,
                'title': change['current']['title'],
                'url': change['current']['url'],
                'source': change['current']['source']
                # 需要添加更多字段
            })
        
        return self._process_documents_batch(documents, 'create', enable_full_processing)
    
    def _process_updated_documents(self, 
                                 updated_changes: List[Dict[str, Any]],
                                 enable_full_processing: bool) -> Dict[str, Any]:
        """处理更新文档"""
        if not updated_changes:
            return {'success': True, 'processed_count': 0, 'errors': []}
        
        logger.info(f"处理 {len(updated_changes)} 个更新文档")
        
        # 提取文档数据
        documents = []
        for change in updated_changes:
            doc_id = change['id']
            # 同样需要获取完整的更新后文档数据
            documents.append({
                'id': doc_id,
                'title': change['current']['title'],
                'url': change['current']['url'],
                'source': change['current']['source']
                # 需要添加更多字段
            })
        
        return self._process_documents_batch(documents, 'update', enable_full_processing)
    
    def _process_deleted_documents(self, 
                                 deleted_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """处理删除文档"""
        if not deleted_changes:
            return {'success': True, 'processed_count': 0, 'errors': []}
        
        logger.info(f"处理 {len(deleted_changes)} 个删除文档")
        
        success_count = 0
        errors = []
        
        for change in deleted_changes:
            doc_id = change['id']
            
            try:
                # 从Elasticsearch删除
                es_success = self.document_indexer.delete_document(doc_id)
                
                # 从向量存储删除
                vector_success = self.vector_manager.delete_document_vector(doc_id)
                
                if es_success or vector_success:
                    success_count += 1
                    logger.debug(f"文档删除成功: {doc_id}")
                else:
                    errors.append(f"文档删除失败: {doc_id}")
                
            except Exception as e:
                error_msg = f"文档删除异常: {doc_id}, 错误: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            'success': len(errors) == 0,
            'processed_count': success_count,
            'errors': errors
        }
    
    def _process_documents_batch(self, 
                               documents: List[Dict[str, Any]],
                               operation: str,
                               enable_full_processing: bool) -> Dict[str, Any]:
        """批量处理文档"""
        if not documents:
            return {'success': True, 'processed_count': 0, 'errors': []}
        
        success_count = 0
        errors = []
        
        try:
            # 分批处理
            for i in range(0, len(documents), self.batch_size):
                batch = documents[i:i + self.batch_size]
                
                batch_result = self._process_single_batch(
                    batch, operation, enable_full_processing
                )
                
                success_count += batch_result['success_count']
                errors.extend(batch_result['errors'])
                
                logger.info(f"批次处理完成: {i + 1}-{min(i + self.batch_size, len(documents))}/{len(documents)}")
            
            return {
                'success': len(errors) == 0,
                'processed_count': success_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"批量处理失败: {str(e)}")
            return {
                'success': False,
                'processed_count': success_count,
                'errors': errors + [str(e)]
            }
    
    def _process_single_batch(self, 
                            batch: List[Dict[str, Any]],
                            operation: str,
                            enable_full_processing: bool) -> Dict[str, Any]:
        """处理单个批次"""
        success_count = 0
        errors = []
        
        try:
            if enable_full_processing:
                # 完整处理：数据清洗 + NLP + 向量化 + 索引
                processed_docs = self._full_process_batch(batch)
            else:
                # 简单处理：仅索引
                processed_docs = batch
            
            # 索引到Elasticsearch
            if processed_docs:
                es_result = self.document_indexer.index_documents(processed_docs)
                
                if es_result['success']:
                    success_count += es_result['success_count']
                    
                    # 如果启用完整处理，还需要处理向量
                    if enable_full_processing:
                        vector_result = self.vector_manager.process_and_store_documents(processed_docs)
                        
                        if not vector_result['success']:
                            errors.append(f"向量处理失败: {vector_result.get('error', '未知错误')}")
                else:
                    errors.extend(es_result['errors'])
            
        except Exception as e:
            errors.append(f"批次处理异常: {str(e)}")
        
        return {
            'success_count': success_count,
            'errors': errors
        }
    
    def _full_process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """完整处理批次（包含所有处理步骤）"""
        try:
            # 使用数据处理管道
            pipeline_result = self.data_pipeline.process_documents(
                batch,
                enable_deduplication=False,  # 增量处理时不需要去重
                enable_quality_filter=True
            )
            
            if pipeline_result and 'processed_documents' in pipeline_result:
                return pipeline_result['processed_documents']
            else:
                logger.warning("数据处理管道返回空结果")
                return batch
                
        except Exception as e:
            logger.error(f"完整处理失败: {str(e)}")
            return batch
    
    def process_single_document(self, 
                              document: Dict[str, Any],
                              operation: str = 'create',
                              enable_full_processing: bool = True) -> Dict[str, Any]:
        """
        处理单个文档
        
        Args:
            document: 文档数据
            operation: 操作类型 ('create', 'update', 'delete')
            enable_full_processing: 是否启用完整处理
            
        Returns:
            处理结果
        """
        start_time = datetime.now()
        
        try:
            if operation == 'delete':
                doc_id = document.get('id') or document.get('_id')
                if not doc_id:
                    return {'success': False, 'error': '缺少文档ID'}
                
                # 删除操作
                es_success = self.document_indexer.delete_document(doc_id)
                vector_success = self.vector_manager.delete_document_vector(doc_id)
                
                return {
                    'success': es_success or vector_success,
                    'operation': operation,
                    'elasticsearch_success': es_success,
                    'vector_success': vector_success,
                    'processing_time': (datetime.now() - start_time).total_seconds()
                }
            
            else:
                # 创建或更新操作
                if enable_full_processing:
                    # 完整处理
                    processed_doc = self.data_pipeline.process_single_document(document)
                else:
                    processed_doc = document
                
                # 索引到Elasticsearch
                doc_id = processed_doc.get('id') or processed_doc.get('_id')
                
                if operation == 'update' and doc_id:
                    es_success = self.document_indexer.update_document(doc_id, processed_doc)
                else:
                    es_success = self.document_indexer.index_document(processed_doc, doc_id)
                
                # 处理向量
                vector_success = True
                if enable_full_processing:
                    if operation == 'update' and doc_id:
                        vector_success = self.vector_manager.update_document_vector(doc_id, processed_doc)
                    else:
                        vector_result = self.vector_manager.process_and_store_documents([processed_doc])
                        vector_success = vector_result.get('success', False)
                
                return {
                    'success': es_success and vector_success,
                    'operation': operation,
                    'elasticsearch_success': es_success,
                    'vector_success': vector_success,
                    'processing_time': (datetime.now() - start_time).total_seconds()
                }
                
        except Exception as e:
            logger.error(f"单文档处理失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'operation': operation,
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
    
    async def process_incremental_changes_async(self, 
                                              new_documents: List[Dict[str, Any]],
                                              **kwargs) -> Dict[str, Any]:
        """异步增量处理"""
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            self.executor,
            self.process_incremental_changes,
            new_documents,
            kwargs.get('time_threshold'),
            kwargs.get('enable_full_processing', True)
        )
        
        return result
    
    def schedule_incremental_processing(self, 
                                     interval_minutes: int = 30,
                                     data_source_callback=None) -> None:
        """
        调度增量处理
        
        Args:
            interval_minutes: 处理间隔（分钟）
            data_source_callback: 数据源回调函数，用于获取新数据
        """
        logger.info(f"启动增量处理调度，间隔: {interval_minutes} 分钟")
        
        def run_scheduled_processing():
            while True:
                try:
                    if data_source_callback:
                        # 获取新数据
                        new_documents = data_source_callback()
                        
                        if new_documents:
                            # 处理增量变更
                            result = self.process_incremental_changes(new_documents)
                            
                            if result['success']:
                                logger.info(f"调度处理完成: {result['summary']}")
                            else:
                                logger.error(f"调度处理失败: {result.get('error', '未知错误')}")
                        else:
                            logger.debug("没有新数据需要处理")
                    
                    # 等待下次处理
                    time.sleep(interval_minutes * 60)
                    
                except Exception as e:
                    logger.error(f"调度处理异常: {str(e)}")
                    time.sleep(60)  # 出错后等待1分钟再重试
        
        # 在后台线程中运行
        import threading
        schedule_thread = threading.Thread(target=run_scheduled_processing, daemon=True)
        schedule_thread.start()
    
    def _update_statistics(self, 
                         processing_results: Dict[str, Any],
                         processing_time: float):
        """更新统计信息"""
        # 统计处理数量
        created_count = processing_results['created']['processed_count']
        updated_count = processing_results['updated']['processed_count']
        deleted_count = processing_results['deleted']['processed_count']
        
        self.stats['created_processed'] += created_count
        self.stats['updated_processed'] += updated_count
        self.stats['deleted_processed'] += deleted_count
        self.stats['total_processed'] += created_count + updated_count + deleted_count
        
        # 统计错误数量
        total_errors = (
            len(processing_results['created']['errors']) +
            len(processing_results['updated']['errors']) +
            len(processing_results['deleted']['errors'])
        )
        self.stats['processing_errors'] += total_errors
        
        # 更新时间统计
        self.stats['total_processing_time'] += processing_time
        self.stats['last_processing_time'] = datetime.now().isoformat()
    
    def _generate_processing_summary(self, 
                                   processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """生成处理摘要"""
        return {
            'created': processing_results['created']['processed_count'],
            'updated': processing_results['updated']['processed_count'],
            'deleted': processing_results['deleted']['processed_count'],
            'total_processed': (
                processing_results['created']['processed_count'] +
                processing_results['updated']['processed_count'] +
                processing_results['deleted']['processed_count']
            ),
            'total_errors': (
                len(processing_results['created']['errors']) +
                len(processing_results['updated']['errors']) +
                len(processing_results['deleted']['errors'])
            )
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 计算平均处理时间
        if stats['total_processed'] > 0:
            stats['avg_processing_time'] = stats['total_processing_time'] / stats['total_processed']
        else:
            stats['avg_processing_time'] = 0.0
        
        # 添加组件统计
        stats['change_detector'] = self.change_detector.get_statistics()
        stats['vector_manager'] = self.vector_manager.get_statistics()
        stats['document_indexer'] = self.document_indexer.get_statistics()
        
        return stats
    
    def reset_statistics(self):
        """重置统计信息"""
        for key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] = 0
            elif key == 'last_processing_time':
                self.stats[key] = None
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
            
            # 清理组件资源
            if hasattr(self.data_pipeline, 'cleanup'):
                self.data_pipeline.cleanup()
            
            if hasattr(self.vector_manager, 'cleanup'):
                self.vector_manager.cleanup()
            
            logger.info("增量处理器资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")
