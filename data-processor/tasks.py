"""
Celery异步任务模块

实现投资情报搜索引擎的核心异步任务：
- 数据处理任务
- 向量生成任务  
- 搜索索引更新任务
- 智能分析任务
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import Celery, Task
from celery.result import AsyncResult
from loguru import logger
import json
import traceback
import sys
import os

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 导入现有的数据处理模块
try:
    from main import DataProcessorManager
    from pipeline import DataProcessingPipeline
    from nlp.nlp_processor import NLPProcessor
    from vector.vector_manager import VectorManager
    from elasticsearch.document_indexer import DocumentIndexer
    from elasticsearch.search_engine import SearchEngine
    from config import config
    logger.info("成功导入所有数据处理模块")
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    # 如果导入失败，我们需要修复依赖问题，而不是简化
    raise

# 创建Celery应用实例
app = Celery('qsou-data-processor')

# Celery配置
app.conf.update(
    broker_url=config.celery_broker_url,
    result_backend=config.celery_result_backend,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_expires=3600,
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 任务路由配置
    task_routes={
        'data-processor.tasks.process_crawled_data': {'queue': 'data_processing'},
        'data-processor.tasks.generate_embeddings': {'queue': 'vector_processing'},
        'data-processor.tasks.update_search_index': {'queue': 'search_indexing'},
        'data-processor.tasks.analyze_intelligence': {'queue': 'intelligence_analysis'},
    },
    
    # 工作进程配置
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
)

# 全局组件实例（延迟初始化）
_processor_manager = None
_pipeline = None
_nlp_processor = None
_vector_manager = None
_document_indexer = None
_search_engine = None


def get_processor_manager() -> DataProcessorManager:
    """获取数据处理管理器实例（单例模式）"""
    global _processor_manager
    if _processor_manager is None:
        _processor_manager = DataProcessorManager()
        # 初始化组件（同步方式）
        try:
            # 创建事件循环来运行异步初始化
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_processor_manager.initialize())
            loop.close()
        except Exception as e:
            logger.error(f"初始化数据处理管理器失败: {str(e)}")
            raise
    return _processor_manager


def get_pipeline() -> DataProcessingPipeline:
    """获取数据处理管道实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = DataProcessingPipeline()
    return _pipeline


def get_nlp_processor() -> NLPProcessor:
    """获取NLP处理器实例"""
    global _nlp_processor
    if _nlp_processor is None:
        _nlp_processor = NLPProcessor()
    return _nlp_processor


def get_vector_manager() -> VectorManager:
    """获取向量管理器实例"""
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorManager()
    return _vector_manager


def get_document_indexer() -> DocumentIndexer:
    """获取文档索引器实例"""
    global _document_indexer
    if _document_indexer is None:
        _document_indexer = DocumentIndexer()
    return _document_indexer


def get_search_engine() -> SearchEngine:
    """获取搜索引擎实例"""
    global _search_engine
    if _search_engine is None:
        _search_engine = SearchEngine()
    return _search_engine


class BaseTask(Task):
    """基础任务类，提供通用的错误处理和日志记录"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的处理"""
        logger.error(f"任务失败: {task_id}, 异常: {str(exc)}")
        logger.error(f"错误详情: {einfo}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的处理"""
        logger.info(f"任务完成: {task_id}, 结果: {type(retval).__name__}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试时的处理"""
        logger.warning(f"任务重试: {task_id}, 异常: {str(exc)}")


@app.task(base=BaseTask, bind=True, max_retries=3, default_retry_delay=60)
def process_crawled_data(self, data_id: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理爬取的数据
    
    Args:
        data_id: 数据唯一标识
        raw_data: 原始爬取数据
        
    Returns:
        Dict包含处理结果和统计信息
    """
    try:
        logger.info(f"开始处理爬取数据: {data_id}")
        
        # 获取数据处理管道
        pipeline = get_pipeline()
        
        # 转换数据格式
        documents = [raw_data] if isinstance(raw_data, dict) else raw_data
        
        # 执行数据处理管道
        result = pipeline.process_documents(
            raw_documents=documents,
            enable_deduplication=True,
            enable_quality_filter=True,
            batch_size=config.batch_size
        )
        
        # 记录处理统计
        stats = result.get('stats', {})
        logger.info(f"数据处理完成: {data_id}, 处理了 {stats.get('total_processed', 0)} 条数据")
        
        # 如果处理成功，触发后续任务
        processed_docs = result.get('processed_documents', [])
        if processed_docs:
            # 异步启动向量生成和索引更新任务
            for doc in processed_docs:
                generate_embeddings.delay(doc['id'], doc)
                update_search_index.delay(doc['id'], doc)
        
        return {
            'status': 'success',
            'data_id': data_id,
            'processed_count': len(processed_docs),
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"处理爬取数据失败: {data_id}, 错误: {str(exc)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        
        # 重试机制
        if self.request.retries < self.max_retries:
            logger.info(f"准备重试任务: {data_id}")
            raise self.retry(exc=exc)
        
        return {
            'status': 'failed',
            'data_id': data_id,
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


@app.task(base=BaseTask, bind=True, max_retries=3, default_retry_delay=30)
def generate_embeddings(self, doc_id: str, document: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成文档向量嵌入
    
    Args:
        doc_id: 文档唯一标识
        document: 处理后的文档数据
        
    Returns:
        Dict包含向量生成结果
    """
    try:
        logger.info(f"开始生成文档向量: {doc_id}")
        
        # 获取向量管理器
        vector_manager = get_vector_manager()
        
        # 提取文本内容
        text_content = document.get('content', '')
        title = document.get('title', '')
        
        # 组合文本（标题 + 内容）
        combined_text = f"{title}\n{text_content}".strip()
        
        if not combined_text:
            raise ValueError(f"文档 {doc_id} 没有有效的文本内容")
        
        # 生成向量嵌入
        embedding_result = vector_manager.generate_embeddings([combined_text])
        
        if not embedding_result or not embedding_result.get('embeddings'):
            raise ValueError(f"向量生成失败: {doc_id}")
        
        embedding = embedding_result['embeddings'][0]
        
        # 构造向量存储的数据
        vector_data = {
            'id': doc_id,
            'vector': embedding,
            'metadata': {
                'title': title,
                'content_preview': text_content[:200] + '...' if len(text_content) > 200 else text_content,
                'source': document.get('source', ''),
                'url': document.get('url', ''),
                'timestamp': document.get('timestamp', datetime.now().isoformat()),
                'category': document.get('category', 'general'),
                'quality_score': document.get('quality_score', 0.0)
            }
        }
        
        # 存储到向量数据库
        storage_result = vector_manager.store_vectors([vector_data])
        
        logger.info(f"文档向量生成并存储完成: {doc_id}")
        
        return {
            'status': 'success',
            'doc_id': doc_id,
            'vector_dimension': len(embedding),
            'storage_result': storage_result,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"生成文档向量失败: {doc_id}, 错误: {str(exc)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        
        # 重试机制
        if self.request.retries < self.max_retries:
            logger.info(f"准备重试向量生成任务: {doc_id}")
            raise self.retry(exc=exc)
        
        return {
            'status': 'failed',
            'doc_id': doc_id,
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


@app.task(base=BaseTask, bind=True, max_retries=3, default_retry_delay=30)
def update_search_index(self, doc_id: str, document: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新搜索索引
    
    Args:
        doc_id: 文档唯一标识
        document: 处理后的文档数据
        
    Returns:
        Dict包含索引更新结果
    """
    try:
        logger.info(f"开始更新搜索索引: {doc_id}")
        
        # 获取文档索引器
        document_indexer = get_document_indexer()
        
        # 准备索引数据
        index_doc = {
            'id': doc_id,
            'title': document.get('title', ''),
            'content': document.get('content', ''),
            'summary': document.get('summary', ''),
            'source': document.get('source', ''),
            'url': document.get('url', ''),
            'timestamp': document.get('timestamp', datetime.now().isoformat()),
            'category': document.get('category', 'general'),
            'tags': document.get('tags', []),
            'quality_score': document.get('quality_score', 0.0),
            'sentiment': document.get('sentiment', {}),
            'entities': document.get('entities', []),
            'keywords': document.get('keywords', [])
        }
        
        # 根据文档类型选择索引
        category = document.get('category', 'general')
        if category == 'news':
            index_name = config.es_news_index
        elif category == 'announcement':
            index_name = config.es_announcements_index
        else:
            index_name = f"{config.es_index_prefix}_general"
        
        # 索引文档
        index_result = document_indexer.index_document(
            index_name=index_name,
            document=index_doc,
            doc_id=doc_id
        )
        
        logger.info(f"搜索索引更新完成: {doc_id}")
        
        return {
            'status': 'success',
            'doc_id': doc_id,
            'index_name': index_name,
            'index_result': index_result,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"更新搜索索引失败: {doc_id}, 错误: {str(exc)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        
        # 重试机制
        if self.request.retries < self.max_retries:
            logger.info(f"准备重试索引更新任务: {doc_id}")
            raise self.retry(exc=exc)
        
        return {
            'status': 'failed',
            'doc_id': doc_id,
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


@app.task(base=BaseTask, bind=True, max_retries=2, default_retry_delay=120)
def analyze_intelligence(self, topic: str, time_range: int = 7, analysis_type: str = 'comprehensive') -> Dict[str, Any]:
    """
    智能情报分析任务
    
    Args:
        topic: 分析主题
        time_range: 时间范围（天数）
        analysis_type: 分析类型
        
    Returns:
        Dict包含分析结果
    """
    try:
        logger.info(f"开始智能情报分析: {topic}, 时间范围: {time_range}天")
        
        # 获取搜索引擎和NLP处理器
        search_engine = get_search_engine()
        nlp_processor = get_nlp_processor()
        
        # 1. 搜索相关文档
        search_query = {
            'query': topic,
            'size': 100,
            'time_range': time_range,
            'sort': 'timestamp:desc'
        }
        
        search_results = search_engine.search_documents(search_query)
        documents = search_results.get('documents', [])
        
        if not documents:
            return {
                'status': 'success',
                'topic': topic,
                'analysis_result': {
                    'summary': f'在指定的{time_range}天时间范围内，未找到与"{topic}"相关的足够信息。',
                    'document_count': 0,
                    'sentiment': {'positive': 0.33, 'neutral': 0.34, 'negative': 0.33, 'score': 0.0},
                    'key_entities': [],
                    'key_themes': [],
                    'timeline_analysis': [],
                    'recommendations': ['扩大搜索时间范围', '调整搜索关键词', '等待更多数据']
                },
                'timestamp': datetime.now().isoformat()
            }
        
        # 2. NLP分析
        texts = [f"{doc.get('title', '')} {doc.get('content', '')}" for doc in documents]
        
        # 情感分析
        sentiment_results = nlp_processor.analyze_sentiment_batch(texts)
        
        # 实体识别
        entity_results = nlp_processor.extract_entities_batch(texts)
        
        # 关键词提取
        keyword_results = nlp_processor.extract_keywords_batch(texts)
        
        # 3. 聚合分析结果
        # 计算整体情感倾向
        sentiments = [s.get('sentiment', 'neutral') for s in sentiment_results]
        sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        sentiment_scores = []
        
        for result in sentiment_results:
            sentiment = result.get('sentiment', 'neutral')
            sentiment_counts[sentiment] += 1
            sentiment_scores.append(result.get('confidence', 0.5))
        
        total_docs = len(documents)
        sentiment_distribution = {
            'positive': sentiment_counts['positive'] / total_docs,
            'neutral': sentiment_counts['neutral'] / total_docs,
            'negative': sentiment_counts['negative'] / total_docs,
            'score': sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        }
        
        # 提取关键实体
        all_entities = []
        for entities in entity_results:
            all_entities.extend(entities.get('entities', []))
        
        # 统计实体频次
        entity_freq = {}
        for entity in all_entities:
            key = f"{entity['text']}_{entity['label']}"
            entity_freq[key] = entity_freq.get(key, 0) + 1
        
        # 取前10个最频繁的实体
        top_entities = sorted(entity_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        key_entities = [{'entity': k.split('_')[0], 'type': k.split('_')[1], 'frequency': v} 
                       for k, v in top_entities]
        
        # 提取关键主题
        all_keywords = []
        for keywords in keyword_results:
            all_keywords.extend(keywords.get('keywords', []))
        
        # 统计关键词频次
        keyword_freq = {}
        for kw in all_keywords:
            keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
        
        # 取前10个关键主题
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        key_themes = [{'theme': k, 'frequency': v} for k, v in top_keywords]
        
        # 时间线分析
        timeline_data = {}
        for doc in documents:
            date = doc.get('timestamp', '')[:10]  # 取日期部分
            if date not in timeline_data:
                timeline_data[date] = {'count': 0, 'sentiment_sum': 0}
            timeline_data[date]['count'] += 1
            # 查找对应的情感分数
            for result in sentiment_results:
                if doc.get('content', '') in result.get('text', ''):
                    timeline_data[date]['sentiment_sum'] += result.get('confidence', 0.5)
                    break
        
        timeline_analysis = []
        for date, data in sorted(timeline_data.items()):
            timeline_analysis.append({
                'date': date,
                'document_count': data['count'],
                'avg_sentiment': data['sentiment_sum'] / data['count'] if data['count'] > 0 else 0.0
            })
        
        # 生成建议
        recommendations = []
        if sentiment_distribution['negative'] > 0.6:
            recommendations.append(f"关于'{topic}'的负面情绪较高，建议密切关注相关风险")
        if sentiment_distribution['positive'] > 0.6:
            recommendations.append(f"关于'{topic}'的正面情绪较高，可关注相关机会")
        if total_docs < 10:
            recommendations.append("相关信息较少，建议扩大搜索范围或延长时间范围")
        
        if not recommendations:
            recommendations.append("情报信息充足，建议继续监控趋势变化")
        
        # 构建分析报告
        analysis_result = {
            'summary': f'在{time_range}天内共分析了{total_docs}篇与"{topic}"相关的文档。'
                      f'整体情感倾向为{"积极" if sentiment_distribution["positive"] > 0.5 else "消极" if sentiment_distribution["negative"] > 0.5 else "中性"}。',
            'document_count': total_docs,
            'sentiment': sentiment_distribution,
            'key_entities': key_entities,
            'key_themes': key_themes,
            'timeline_analysis': timeline_analysis,
            'recommendations': recommendations
        }
        
        logger.info(f"智能情报分析完成: {topic}, 分析了{total_docs}篇文档")
        
        return {
            'status': 'success',
            'topic': topic,
            'time_range': time_range,
            'analysis_type': analysis_type,
            'analysis_result': analysis_result,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"智能情报分析失败: {topic}, 错误: {str(exc)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        
        # 重试机制
        if self.request.retries < self.max_retries:
            logger.info(f"准备重试智能分析任务: {topic}")
            raise self.retry(exc=exc)
        
        return {
            'status': 'failed',
            'topic': topic,
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


# 辅助任务：健康检查
@app.task
def health_check() -> Dict[str, Any]:
    """Celery健康检查任务"""
    try:
        return {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'worker_id': app.control.inspect().active_queues(),
            'config': {
                'broker': app.conf.broker_url,
                'result_backend': app.conf.result_backend
            }
        }
    except Exception as exc:
        return {
            'status': 'unhealthy',
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


# 辅助任务：清理过期结果
@app.task
def cleanup_expired_results() -> Dict[str, Any]:
    """清理过期的任务结果"""
    try:
        # 获取所有活跃的任务结果
        inspect = app.control.inspect()
        active_tasks = inspect.active()
        
        cleanup_count = 0
        # 这里可以添加具体的清理逻辑
        
        logger.info(f"清理完成，清理了 {cleanup_count} 个过期结果")
        
        return {
            'status': 'success',
            'cleanup_count': cleanup_count,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as exc:
        logger.error(f"清理过期结果失败: {str(exc)}")
        return {
            'status': 'failed',
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


# 任务状态查询函数
def get_task_status(task_id: str) -> Dict[str, Any]:
    """获取任务状态"""
    result = AsyncResult(task_id, app=app)
    return {
        'task_id': task_id,
        'status': result.status,
        'result': result.result if result.ready() else None,
        'traceback': result.traceback if result.failed() else None
    }


# 批量任务提交函数
def submit_batch_processing(data_items: List[Dict[str, Any]]) -> List[str]:
    """批量提交数据处理任务"""
    task_ids = []
    for item in data_items:
        data_id = item.get('id', f"batch_{datetime.now().timestamp()}")
        task = process_crawled_data.delay(data_id, item)
        task_ids.append(task.id)
        logger.info(f"已提交批量处理任务: {data_id} -> {task.id}")
    
    return task_ids


if __name__ == '__main__':
    # 用于测试的命令行入口
    app.start()
