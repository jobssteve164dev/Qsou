"""
数据处理主模块

整合所有数据处理功能：
- 数据处理管道
- NLP处理
- 向量化和存储
- Elasticsearch索引
- 增量更新
"""
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime
import asyncio

# 导入各个模块
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from pipeline import DataProcessingPipeline
from nlp.nlp_processor import NLPProcessor
from vector.vector_manager import VectorManager
from es_indexing.index_manager import IndexManager
from es_indexing.document_indexer import DocumentIndexer
from es_indexing.search_engine import SearchEngine
from incremental.sync_manager import SyncManager
from config import config


class DataProcessorManager:
    """数据处理管理器"""
    
    def __init__(self):
        """初始化数据处理管理器"""
        # 初始化各个组件
        self.pipeline = DataProcessingPipeline()
        self.nlp_processor = NLPProcessor()
        self.vector_manager = VectorManager()
        self.index_manager = IndexManager()
        self.document_indexer = DocumentIndexer()
        self.search_engine = SearchEngine()
        self.sync_manager = SyncManager()
        
        # 管理器状态
        self.initialized = False
        self.components_status = {}
        
        logger.info("数据处理管理器初始化完成")
    
    async def initialize(self) -> Dict[str, Any]:
        """
        初始化所有组件
        
        Returns:
            初始化结果
        """
        logger.info("开始初始化数据处理系统")
        
        initialization_results = {}
        
        try:
            # 1. 初始化Elasticsearch索引
            logger.info("步骤 1/5: 初始化Elasticsearch索引")
            es_result = self.index_manager.create_standard_indices()
            initialization_results['elasticsearch'] = es_result
            
            # 2. 初始化向量存储
            logger.info("步骤 2/5: 初始化向量存储")
            vector_health = self.vector_manager.health_check()
            initialization_results['vector_store'] = vector_health
            
            # 3. 验证NLP组件
            logger.info("步骤 3/5: 验证NLP组件")
            nlp_stats = self.nlp_processor.get_processing_statistics()
            initialization_results['nlp_processor'] = nlp_stats
            
            # 4. 验证数据处理管道
            logger.info("步骤 4/5: 验证数据处理管道")
            pipeline_stats = self.pipeline.get_processing_statistics()
            initialization_results['data_pipeline'] = pipeline_stats
            
            # 5. 验证搜索引擎
            logger.info("步骤 5/5: 验证搜索引擎")
            search_stats = self.search_engine.get_search_statistics()
            initialization_results['search_engine'] = search_stats
            
            # 检查整体健康状态
            self.components_status = await self._check_components_health()
            
            # 判断初始化是否成功
            all_healthy = all(
                status.get('status') == 'healthy' 
                for status in self.components_status.values()
            )
            
            if all_healthy:
                self.initialized = True
                logger.info("数据处理系统初始化成功")
            else:
                logger.warning("数据处理系统初始化完成，但部分组件存在问题")
            
            return {
                'success': all_healthy,
                'initialized': self.initialized,
                'components_status': self.components_status,
                'initialization_results': initialization_results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"数据处理系统初始化失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'components_status': self.components_status,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _check_components_health(self) -> Dict[str, Any]:
        """检查组件健康状态"""
        health_status = {}
        
        # 检查向量管理器
        try:
            vector_health = self.vector_manager.health_check()
            health_status['vector_manager'] = vector_health
        except Exception as e:
            health_status['vector_manager'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # 检查Elasticsearch
        try:
            cluster_health = self.index_manager.get_cluster_health()
            health_status['elasticsearch'] = {
                'status': 'healthy' if cluster_health.get('status') in ['green', 'yellow'] else 'unhealthy',
                'cluster_health': cluster_health
            }
        except Exception as e:
            health_status['elasticsearch'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # 检查NLP处理器
        try:
            nlp_stats = self.nlp_processor.get_processing_statistics()
            health_status['nlp_processor'] = {
                'status': 'healthy',
                'statistics': nlp_stats
            }
        except Exception as e:
            health_status['nlp_processor'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # 检查数据处理管道
        try:
            pipeline_stats = self.pipeline.get_processing_statistics()
            health_status['data_pipeline'] = {
                'status': 'healthy',
                'statistics': pipeline_stats
            }
        except Exception as e:
            health_status['data_pipeline'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        return health_status
    
    async def process_documents_full_pipeline(self, 
                                            documents: List[Dict[str, Any]],
                                            enable_elasticsearch: bool = True,
                                            enable_vector_store: bool = True) -> Dict[str, Any]:
        """
        完整管道处理文档
        
        Args:
            documents: 文档列表
            enable_elasticsearch: 是否启用Elasticsearch索引
            enable_vector_store: 是否启用向量存储
            
        Returns:
            处理结果
        """
        if not self.initialized:
            return {
                'success': False,
                'error': '系统未初始化，请先调用initialize()'
            }
        
        logger.info(f"开始完整管道处理 {len(documents)} 个文档")
        
        start_time = datetime.now()
        
        try:
            # 1. 数据处理管道（清洗、NLP、质量评估）
            logger.info("步骤 1/3: 数据处理管道")
            pipeline_result = self.pipeline.process_documents(
                documents,
                enable_deduplication=True,
                enable_quality_filter=True
            )
            
            if not pipeline_result or not pipeline_result.get('processed_documents'):
                return {
                    'success': False,
                    'error': '数据处理管道失败',
                    'pipeline_result': pipeline_result
                }
            
            processed_documents = pipeline_result['processed_documents']
            logger.info(f"数据处理完成，有效文档: {len(processed_documents)}")
            
            # 2. Elasticsearch索引
            es_result = None
            if enable_elasticsearch:
                logger.info("步骤 2/3: Elasticsearch索引")
                es_result = self.document_indexer.index_documents(processed_documents)
                
                if not es_result['success']:
                    logger.warning(f"Elasticsearch索引失败: {es_result}")
            
            # 3. 向量存储
            vector_result = None
            if enable_vector_store:
                logger.info("步骤 3/3: 向量存储")
                vector_result = self.vector_manager.process_and_store_documents(processed_documents)
                
                if not vector_result['success']:
                    logger.warning(f"向量存储失败: {vector_result}")
            
            # 计算处理时间
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # 生成结果
            result = {
                'success': True,
                'processing_time': processing_time,
                'input_documents': len(documents),
                'processed_documents': len(processed_documents),
                'pipeline_result': pipeline_result,
                'elasticsearch_result': es_result,
                'vector_result': vector_result,
                'timestamp': end_time.isoformat()
            }
            
            logger.info(f"完整管道处理完成，耗时: {processing_time:.2f}秒")
            
            return result
            
        except Exception as e:
            logger.error(f"完整管道处理失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
    
    async def search_documents(self, 
                             query: str,
                             search_type: str = "hybrid",
                             limit: int = 10,
                             filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        搜索文档
        
        Args:
            query: 搜索查询
            search_type: 搜索类型 ("elasticsearch", "vector", "hybrid")
            limit: 返回结果数量
            filters: 过滤条件
            
        Returns:
            搜索结果
        """
        if not self.initialized:
            return {
                'success': False,
                'error': '系统未初始化'
            }
        
        logger.info(f"执行搜索: '{query}', 类型: {search_type}")
        
        try:
            if search_type == "elasticsearch":
                # 纯Elasticsearch搜索
                result = self.search_engine.search(
                    query=query,
                    size=limit,
                    filters=filters
                )
                
            elif search_type == "vector":
                # 纯向量搜索
                result = self.vector_manager.search(
                    query=query,
                    search_type="semantic",
                    limit=limit,
                    filters=filters
                )
                
            elif search_type == "hybrid":
                # 混合搜索
                result = self.vector_manager.search(
                    query=query,
                    search_type="hybrid",
                    limit=limit,
                    filters=filters
                )
                
            else:
                return {
                    'success': False,
                    'error': f'不支持的搜索类型: {search_type}'
                }
            
            logger.info(f"搜索完成，返回 {len(result.get('documents', []))} 个结果")
            
            return {
                'success': True,
                'search_type': search_type,
                'query': query,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        stats = {
            'initialized': self.initialized,
            'components_status': self.components_status,
            'timestamp': datetime.now().isoformat()
        }
        
        # 获取各组件统计
        try:
            stats['pipeline'] = self.pipeline.get_processing_statistics()
        except Exception as e:
            stats['pipeline'] = {'error': str(e)}
        
        try:
            stats['nlp_processor'] = self.nlp_processor.get_processing_statistics()
        except Exception as e:
            stats['nlp_processor'] = {'error': str(e)}
        
        try:
            stats['vector_manager'] = self.vector_manager.get_statistics()
        except Exception as e:
            stats['vector_manager'] = {'error': str(e)}
        
        try:
            stats['document_indexer'] = self.document_indexer.get_statistics()
        except Exception as e:
            stats['document_indexer'] = {'error': str(e)}
        
        try:
            stats['search_engine'] = self.search_engine.get_search_statistics()
        except Exception as e:
            stats['search_engine'] = {'error': str(e)}
        
        try:
            stats['sync_manager'] = self.sync_manager.get_sync_status()
        except Exception as e:
            stats['sync_manager'] = {'error': str(e)}
        
        return stats
    
    async def run_system_test(self) -> Dict[str, Any]:
        """运行系统测试"""
        logger.info("开始运行系统测试")
        
        test_results = {
            'overall_success': True,
            'tests': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # 测试文档
        test_documents = [
            {
                'title': '测试新闻标题：A股市场今日大涨',
                'content': '今日A股市场表现强劲，上证指数上涨2.5%，深证成指上涨3.1%。科技股领涨，新能源汽车板块表现突出。',
                'url': 'https://test.example.com/news/1',
                'source': '测试财经',
                'publish_time': datetime.now().isoformat()
            },
            {
                'title': '测试公告：某公司发布季度财报',
                'content': '某上市公司发布2024年第三季度财报，营业收入同比增长15%，净利润同比增长20%。',
                'url': 'https://test.example.com/announcement/1',
                'source': '测试公告',
                'publish_time': datetime.now().isoformat()
            }
        ]
        
        try:
            # 1. 测试完整处理管道
            logger.info("测试 1/4: 完整处理管道")
            pipeline_test = await self.process_documents_full_pipeline(test_documents)
            test_results['tests']['full_pipeline'] = pipeline_test
            
            if not pipeline_test['success']:
                test_results['overall_success'] = False
            
            # 2. 测试搜索功能
            logger.info("测试 2/4: 搜索功能")
            search_test = await self.search_documents("A股 上涨", "hybrid", 5)
            test_results['tests']['search'] = search_test
            
            if not search_test['success']:
                test_results['overall_success'] = False
            
            # 3. 测试健康检查
            logger.info("测试 3/4: 健康检查")
            health_check = await self._check_components_health()
            test_results['tests']['health_check'] = health_check
            
            # 4. 测试统计信息
            logger.info("测试 4/4: 统计信息")
            stats_test = self.get_system_statistics()
            test_results['tests']['statistics'] = {
                'success': True,
                'data': stats_test
            }
            
            logger.info(f"系统测试完成，总体结果: {'成功' if test_results['overall_success'] else '失败'}")
            
        except Exception as e:
            logger.error(f"系统测试失败: {str(e)}")
            test_results['overall_success'] = False
            test_results['error'] = str(e)
        
        return test_results
    
    def cleanup(self):
        """清理所有组件资源"""
        logger.info("开始清理数据处理系统资源")
        
        try:
            # 清理各个组件
            if hasattr(self.pipeline, 'cleanup'):
                self.pipeline.cleanup()
            
            if hasattr(self.vector_manager, 'cleanup'):
                self.vector_manager.cleanup()
            
            if hasattr(self.sync_manager, 'cleanup'):
                self.sync_manager.cleanup()
            
            logger.info("数据处理系统资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")


# 全局数据处理管理器实例
data_processor_manager = DataProcessorManager()
