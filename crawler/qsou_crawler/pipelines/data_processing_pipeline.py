"""
爬虫数据管道 - 连接数据处理系统

将爬虫采集的数据发送到数据处理系统进行清洗、分析和索引
"""

import logging
from typing import Dict, Any
from scrapy import Item
from scrapy.exceptions import DropItem
from celery import Celery
import time

from qsou_crawler.items import NewsArticleItem, CompanyAnnouncementItem
from qsou_data import DataAssetStore


class DataProcessingPipeline:
    """数据处理管道"""
    
    def __init__(self, asset_store=None, batch_size=10, dispatch_enabled=True):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.asset_store = asset_store or DataAssetStore()
        self.dispatch_enabled = dispatch_enabled
        
        # 初始化Celery客户端
        self.celery_app = None
        if self.dispatch_enabled:
            self._initialize_celery()
        
        self.batch_size = batch_size
        self.batch_items = []
        
        # 统计信息
        self.stats = {
            'processed': 0,
            'dropped': 0,
            'errors': 0
        }

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            asset_store=DataAssetStore(),
            batch_size=crawler.settings.getint('QSOU_OUTBOX_BATCH_SIZE', 10),
            dispatch_enabled=crawler.settings.getbool('QSOU_OUTBOX_DISPATCH_ENABLED', True),
        )
    
    def _initialize_celery(self):
        """初始化Celery连接"""
        try:
            import os
            self.celery_app = Celery('qsou-data-processor')
            self.celery_app.config_from_object({
                'broker_url': os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'),
                'result_backend': os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2'),
                'task_serializer': 'json',
                'result_serializer': 'json',
                'accept_content': ['json'],
                'timezone': 'Asia/Shanghai',
                'enable_utc': True,
            })
            self.logger.info("Celery连接初始化成功")
        except Exception as e:
            self.logger.error(f"Celery连接初始化失败: {str(e)}")
            self.celery_app = None
    
    def process_item(self, item: Item, spider) -> Item:
        """处理单个项目"""
        try:
            # 数据验证
            if not self.validate_item(item):
                self.stats['dropped'] += 1
                raise DropItem(f"数据验证失败: {item.get('url', 'unknown')}")
            
            # 原始响应已在下载器中间件归档；此处登记标准文档和可靠待处理记录。
            standard_document = self.asset_store.register_document(self.convert_item_to_dict(item))
            self.batch_items.append(standard_document)
            
            # 如果达到批次大小，发送到数据处理系统
            if len(self.batch_items) >= self.batch_size:
                self.send_batch_to_processor()
            
            self.stats['processed'] += 1
            return item
            
        except Exception as e:
            self.logger.error(f"处理项目失败: {str(e)}")
            self.stats['errors'] += 1
            raise DropItem(f"处理失败: {str(e)}")
    
    def close_spider(self, spider):
        """爬虫关闭时处理剩余批次"""
        if self.batch_items:
            self.send_batch_to_processor()
        
        # 输出统计信息
        self.logger.info(f"数据处理管道统计: {self.stats}")

    def open_spider(self, spider):
        """优先恢复上次未成功提交的待处理文档。"""
        if self.dispatch_enabled:
            self.dispatch_pending()
    
    def validate_item(self, item: Item) -> bool:
        """验证数据项"""
        # 检查必要字段
        if not item.get('title') or not item.get('content'):
            return False
        
        # 检查内容长度
        if len(item.get('content', '')) < 50:
            return False
        
        # 检查URL
        if not item.get('url'):
            return False
        
        return True
    
    def send_batch_to_processor(self):
        """发送批次数据到数据处理系统"""
        if not self.batch_items:
            return
        
        try:
            batch_data = list(self.batch_items)

            if not self.dispatch_enabled:
                self.logger.info("派生处理未启用，文档已安全保存在待处理队列")
                return

            import uuid
            trace_id = str(uuid.uuid4())
            self._dispatch_documents(batch_data, trace_id)
            
        except Exception as e:
            self.logger.error(f"发送数据到处理系统失败: {str(e)}")
            self.stats['errors'] += len(self.batch_items)
            self.asset_store.mark_failed(
                [document.get('content_version_id') for document in self.batch_items],
                str(e),
            )
        finally:
            # 内存批次可清空；SQLite 待处理记录只在提交成功后改变状态。
            self.batch_items = []

    def dispatch_pending(self):
        """重试持久化队列，避免上一次 Celery 故障造成数据丢失。"""
        pending = self.asset_store.pending_documents(self.batch_size)
        if not pending:
            return
        try:
            import uuid
            self._dispatch_documents(pending, str(uuid.uuid4()))
        except Exception as exc:
            self.asset_store.mark_failed(
                [document.get('content_version_id') for document in pending],
                str(exc),
            )
            self.logger.error(f"恢复待处理文档失败: {exc}")

    def _dispatch_documents(self, documents, trace_id):
        if not self.celery_app:
            raise RuntimeError("Celery客户端未初始化")
        if not documents:
            return

        self.logger.info(
            "发送批次到处理系统",
            extra={'trace_id': trace_id, 'items': len(documents)},
        )
        batch_id = f"batch_{len(documents)}_{int(time.time())}"
        result = self.celery_app.send_task(
            'tasks.process_crawled_data',
            args=[batch_id, documents],
            queue='data_processing',
        )
        content_version_ids = [document['content_version_id'] for document in documents]
        self.asset_store.mark_dispatched(content_version_ids, result.id)
        self.logger.info(
            f"成功提交 {len(documents)} 条数据到处理系统",
            extra={'trace_id': trace_id, 'task_id': result.id},
        )
    
    def convert_item_to_dict(self, item: Item) -> Dict[str, Any]:
        """将Scrapy项目转换为字典"""
        if isinstance(item, NewsArticleItem):
            metadata = dict(item.get('metadata') or {})
            metadata.update({
                'crawler': 'financial_news_spider',
                'domain': self.extract_domain(item.get('url', '')),
                'language': 'zh-CN'
            })
            return {
                'id': self.generate_item_id(item),
                'type': 'news',
                'title': item.get('title', ''),
                'content': item.get('content', ''),
                'url': item.get('url', ''),
                'source': item.get('source', ''),
                'publish_time': item.get('publish_time') or item.get('published_at', ''),
                'author': item.get('author', ''),
                'tags': item.get('tags', []),
                'category': item.get('category', ''),
                'crawl_time': item.get('crawl_time') or item.get('crawled_at', ''),
                'content_length': item.get('content_length', 0),
                'metadata': metadata,
                'raw_object_id': metadata.get('raw_object_id'),
                'source_id': metadata.get('source_id'),
                'fetched_at': metadata.get('fetched_at'),
                'parser_version': metadata.get('parser_version'),
            }
        elif isinstance(item, CompanyAnnouncementItem):
            metadata = dict(item.get('metadata') or {})
            metadata.update({
                'crawler': 'company_announcement_spider',
                'domain': self.extract_domain(item.get('url', '')),
                'language': 'zh-CN'
            })
            return {
                'id': self.generate_item_id(item),
                'type': 'announcement',
                'title': item.get('title', ''),
                'content': item.get('content', ''),
                'url': item.get('url', ''),
                'source': item.get('source', ''),
                'exchange': item.get('exchange', ''),
                'company_name': item.get('company_name', ''),
                'stock_code': item.get('stock_code', ''),
                'announcement_type': item.get('announcement_type', ''),
                'publish_time': item.get('publish_time', ''),
                'announcement_id': item.get('announcement_id', ''),
                'crawl_time': item.get('crawl_time', ''),
                'content_length': item.get('content_length', 0),
                'is_important': item.get('is_important', False),
                'metadata': metadata,
                'raw_object_id': metadata.get('raw_object_id'),
                'source_id': metadata.get('source_id'),
                'fetched_at': metadata.get('fetched_at'),
                'parser_version': metadata.get('parser_version'),
            }
        else:
            # 通用转换
            return dict(item)
    
    def generate_item_id(self, item: Item) -> str:
        """生成项目唯一ID"""
        import hashlib
        
        # 使用URL和标题生成唯一ID
        content = f"{item.get('url', '')}{item.get('title', '')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        from urllib.parse import urlparse
        return urlparse(url).netloc


class ValidationPipeline:
    """数据验证管道"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stats = {
            'validated': 0,
            'dropped': 0
        }
    
    def process_item(self, item: Item, spider) -> Item:
        """验证数据项"""
        try:
            if self.validate_item(item):
                self.stats['validated'] += 1
                return item
            else:
                self.stats['dropped'] += 1
                raise DropItem(f"数据验证失败: {item.get('url', 'unknown')}")
        except Exception as e:
            self.logger.error(f"验证项目失败: {str(e)}")
            raise DropItem(f"验证失败: {str(e)}")
    
    def validate_item(self, item: Item) -> bool:
        """验证数据项"""
        # 基本字段检查
        if not item.get('title') or not item.get('content'):
            return False
        
        # 内容长度检查
        if len(item.get('content', '')) < 50:
            return False
        
        # URL格式检查
        url = item.get('url', '')
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        # 标题长度检查
        if len(item.get('title', '')) < 5:
            return False
        
        return True
    
    def close_spider(self, spider):
        """输出验证统计"""
        self.logger.info(f"数据验证统计: {self.stats}")


class DuplicationPipeline:
    """去重管道"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.seen_urls = set()
        self.seen_titles = set()
        self.stats = {
            'processed': 0,
            'duplicates': 0
        }
    
    def process_item(self, item: Item, spider) -> Item:
        """去重处理"""
        try:
            url = item.get('url', '')
            title = item.get('title', '')
            
            # URL去重
            if url in self.seen_urls:
                self.stats['duplicates'] += 1
                raise DropItem(f"URL重复: {url}")
            
            # 标题去重（简单实现）
            title_hash = hash(title)
            if title_hash in self.seen_titles:
                self.stats['duplicates'] += 1
                raise DropItem(f"标题重复: {title}")
            
            # 添加到已见集合
            self.seen_urls.add(url)
            self.seen_titles.add(title_hash)
            
            self.stats['processed'] += 1
            return item
            
        except Exception as e:
            self.logger.error(f"去重处理失败: {str(e)}")
            raise DropItem(f"去重失败: {str(e)}")
    
    def close_spider(self, spider):
        """输出去重统计"""
        self.logger.info(f"去重统计: {self.stats}")


class StatisticsPipeline:
    """统计管道"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stats = {
            'total_items': 0,
            'news_items': 0,
            'announcement_items': 0,
            'by_source': {},
            'by_category': {},
            'content_lengths': []
        }
    
    def process_item(self, item: Item, spider) -> Item:
        """统计处理"""
        try:
            self.stats['total_items'] += 1
            
            # 按类型统计
            if isinstance(item, NewsArticleItem):
                self.stats['news_items'] += 1
            elif isinstance(item, CompanyAnnouncementItem):
                self.stats['announcement_items'] += 1
            
            # 按来源统计
            source = item.get('source', 'unknown')
            self.stats['by_source'][source] = self.stats['by_source'].get(source, 0) + 1
            
            # 按分类统计
            category = item.get('category', 'unknown')
            self.stats['by_category'][category] = self.stats['by_category'].get(category, 0) + 1
            
            # 内容长度统计
            content_length = item.get('content_length', 0)
            if content_length > 0:
                self.stats['content_lengths'].append(content_length)
            
            return item
            
        except Exception as e:
            self.logger.error(f"统计处理失败: {str(e)}")
            return item
    
    def close_spider(self, spider):
        """输出统计信息"""
        self.logger.info("=== 爬虫统计信息 ===")
        self.logger.info(f"总项目数: {self.stats['total_items']}")
        self.logger.info(f"新闻项目: {self.stats['news_items']}")
        self.logger.info(f"公告项目: {self.stats['announcement_items']}")
        
        self.logger.info("按来源统计:")
        for source, count in self.stats['by_source'].items():
            self.logger.info(f"  {source}: {count}")
        
        self.logger.info("按分类统计:")
        for category, count in self.stats['by_category'].items():
            self.logger.info(f"  {category}: {count}")
        
        if self.stats['content_lengths']:
            avg_length = sum(self.stats['content_lengths']) / len(self.stats['content_lengths'])
            self.logger.info(f"平均内容长度: {avg_length:.2f} 字符")
