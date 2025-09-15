"""
数据处理管道

统一协调各个处理器，实现完整的数据处理流程：
1. 数据清洗
2. 内容提取
3. 去重处理
4. 质量评估
5. 结果输出
"""
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

from .processors import DataCleaner, ContentExtractor, Deduplicator, QualityAssessor
from .config import config


class DataProcessingPipeline:
    """数据处理管道"""
    
    def __init__(self):
        # 初始化各个处理器
        self.cleaner = DataCleaner()
        self.extractor = ContentExtractor()
        self.deduplicator = Deduplicator()
        self.quality_assessor = QualityAssessor()
        
        # 处理统计
        self.stats = {
            'total_processed': 0,
            'cleaned': 0,
            'extracted': 0,
            'deduplicated': 0,
            'quality_assessed': 0,
            'high_quality': 0,
            'duplicates_removed': 0,
            'processing_time': 0.0
        }
        
        # 线程池用于并行处理
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def process_documents(self, raw_documents: List[Dict[str, Any]], 
                         enable_deduplication: bool = True,
                         enable_quality_filter: bool = True,
                         batch_size: int = None) -> Dict[str, Any]:
        """
        处理文档列表
        
        Args:
            raw_documents: 原始文档列表
            enable_deduplication: 是否启用去重
            enable_quality_filter: 是否启用质量过滤
            batch_size: 批处理大小
            
        Returns:
            处理结果字典
        """
        start_time = datetime.now()
        logger.info(f"开始处理 {len(raw_documents)} 个文档")
        
        if not raw_documents:
            return self._create_empty_result()
        
        # 重置统计信息
        self._reset_stats()
        self.stats['total_processed'] = len(raw_documents)
        
        try:
            # 第一步：数据清洗
            logger.info("步骤 1/5: 数据清洗")
            cleaned_documents = self._process_batch(
                raw_documents, 
                self.cleaner.batch_clean,
                batch_size or config.batch_size
            )
            self.stats['cleaned'] = len(cleaned_documents)
            
            # 第二步：内容特征提取
            logger.info("步骤 2/5: 内容特征提取")
            extracted_documents = self._process_batch(
                cleaned_documents,
                self.extractor.batch_extract,
                batch_size or config.batch_size
            )
            self.stats['extracted'] = len(extracted_documents)
            
            # 第三步：去重处理
            if enable_deduplication:
                logger.info("步骤 3/5: 去重处理")
                unique_documents, duplicate_documents = self.deduplicator.deduplicate_documents(extracted_documents)
                self.stats['deduplicated'] = len(unique_documents)
                self.stats['duplicates_removed'] = len(duplicate_documents)
            else:
                unique_documents = extracted_documents
                duplicate_documents = []
                self.stats['deduplicated'] = len(unique_documents)
            
            # 第四步：质量评估
            logger.info("步骤 4/5: 质量评估")
            assessed_documents = self.quality_assessor.batch_assess(unique_documents)
            self.stats['quality_assessed'] = len(assessed_documents)
            
            # 第五步：质量过滤（可选）
            if enable_quality_filter:
                logger.info("步骤 5/5: 质量过滤")
                final_documents = self.quality_assessor.filter_high_quality_documents(assessed_documents)
                low_quality_documents = [doc for doc in assessed_documents if doc not in final_documents]
                self.stats['high_quality'] = len(final_documents)
            else:
                final_documents = assessed_documents
                low_quality_documents = []
                self.stats['high_quality'] = len(final_documents)
            
            # 计算处理时间
            end_time = datetime.now()
            self.stats['processing_time'] = (end_time - start_time).total_seconds()
            
            # 创建处理结果
            result = {
                'processed_documents': final_documents,
                'duplicate_documents': duplicate_documents,
                'low_quality_documents': low_quality_documents,
                'statistics': self.stats.copy(),
                'processing_info': {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'pipeline_version': '1.0.0',
                    'config_used': {
                        'enable_deduplication': enable_deduplication,
                        'enable_quality_filter': enable_quality_filter,
                        'batch_size': batch_size or config.batch_size
                    }
                }
            }
            
            logger.info(f"文档处理完成，最终输出 {len(final_documents)} 个高质量文档")
            self._log_processing_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"文档处理管道失败: {str(e)}")
            raise
    
    def _process_batch(self, documents: List[Dict[str, Any]], 
                      processor_func, batch_size: int) -> List[Dict[str, Any]]:
        """批量处理文档"""
        if len(documents) <= batch_size:
            return processor_func(documents)
        
        # 分批处理
        processed_documents = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_result = processor_func(batch)
            processed_documents.extend(batch_result)
            
            logger.debug(f"批次处理完成: {i + 1}-{min(i + batch_size, len(documents))}/{len(documents)}")
        
        return processed_documents
    
    def process_single_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个文档"""
        try:
            # 数据清洗
            cleaned_doc = self.cleaner.clean_document(document)
            
            # 内容提取
            extracted_doc = self.extractor.extract_content_features(cleaned_doc)
            
            # 质量评估
            assessed_doc = self.quality_assessor.assess_document_quality(extracted_doc)
            
            return assessed_doc
            
        except Exception as e:
            logger.error(f"单文档处理失败: {str(e)}")
            return document
    
    async def process_documents_async(self, raw_documents: List[Dict[str, Any]], 
                                    **kwargs) -> Dict[str, Any]:
        """异步处理文档"""
        loop = asyncio.get_event_loop()
        
        # 在线程池中执行同步处理
        result = await loop.run_in_executor(
            self.executor,
            self.process_documents,
            raw_documents,
            kwargs.get('enable_deduplication', True),
            kwargs.get('enable_quality_filter', True),
            kwargs.get('batch_size', None)
        )
        
        return result
    
    def validate_input_documents(self, documents: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """验证输入文档格式"""
        errors = []
        
        if not isinstance(documents, list):
            errors.append("输入必须是列表类型")
            return False, errors
        
        if not documents:
            errors.append("文档列表不能为空")
            return False, errors
        
        # 检查文档格式
        required_fields = ['title', 'content']
        for i, doc in enumerate(documents[:10]):  # 只检查前10个文档
            if not isinstance(doc, dict):
                errors.append(f"文档 {i} 必须是字典类型")
                continue
            
            for field in required_fields:
                if field not in doc:
                    errors.append(f"文档 {i} 缺少必需字段: {field}")
        
        return len(errors) == 0, errors
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return {
            'current_stats': self.stats.copy(),
            'deduplication_stats': self.deduplicator.get_deduplication_stats(),
            'pipeline_info': {
                'version': '1.0.0',
                'processors': ['cleaner', 'extractor', 'deduplicator', 'quality_assessor']
            }
        }
    
    def _reset_stats(self):
        """重置统计信息"""
        for key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] = 0
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """创建空结果"""
        return {
            'processed_documents': [],
            'duplicate_documents': [],
            'low_quality_documents': [],
            'statistics': self.stats.copy(),
            'processing_info': {
                'start_time': datetime.now().isoformat(),
                'end_time': datetime.now().isoformat(),
                'pipeline_version': '1.0.0',
                'config_used': {}
            }
        }
    
    def _log_processing_summary(self, result: Dict[str, Any]):
        """记录处理摘要"""
        stats = result['statistics']
        
        summary = f"""
数据处理管道执行摘要:
================================
总文档数: {stats['total_processed']}
清洗完成: {stats['cleaned']}
特征提取: {stats['extracted']}
去重处理: {stats['deduplicated']} (移除重复: {stats['duplicates_removed']})
质量评估: {stats['quality_assessed']}
高质量文档: {stats['high_quality']}
处理时间: {stats['processing_time']:.2f} 秒
平均处理速度: {stats['total_processed'] / max(stats['processing_time'], 0.1):.1f} 文档/秒
================================
        """
        
        logger.info(summary)
    
    def export_processing_report(self, result: Dict[str, Any], output_path: str):
        """导出处理报告"""
        try:
            report = {
                'summary': result['statistics'],
                'processing_info': result['processing_info'],
                'document_samples': {
                    'processed_sample': result['processed_documents'][:3] if result['processed_documents'] else [],
                    'duplicate_sample': result['duplicate_documents'][:3] if result['duplicate_documents'] else [],
                    'low_quality_sample': result['low_quality_documents'][:3] if result['low_quality_documents'] else []
                }
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"处理报告已导出到: {output_path}")
            
        except Exception as e:
            logger.error(f"报告导出失败: {str(e)}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
            logger.info("数据处理管道资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")


# 全局管道实例
pipeline = DataProcessingPipeline()
