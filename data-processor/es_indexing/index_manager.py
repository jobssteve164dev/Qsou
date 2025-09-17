"""
Elasticsearch索引管理器

负责：
- 索引创建和删除
- 索引模板管理
- 映射配置
- 索引策略管理
"""
from typing import Dict, Any, List, Optional
from loguru import logger
import json
from datetime import datetime

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.exceptions import RequestError, NotFoundError
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False
    logger.warning("elasticsearch未安装，索引管理功能不可用")

from config import config


class IndexManager:
    """Elasticsearch索引管理器"""
    
    def __init__(self, es_url: str = None):
        """
        初始化索引管理器
        
        Args:
            es_url: Elasticsearch服务URL
        """
        self.es_url = es_url or config.elasticsearch_url
        self.client = None
        
        # 索引配置
        self.index_settings = self._get_default_index_settings()
        self.index_mappings = self._get_default_index_mappings()
        
        # 初始化Elasticsearch客户端
        self._initialize_client()
        
        logger.info("Elasticsearch索引管理器初始化完成")
    
    def _initialize_client(self):
        """初始化Elasticsearch客户端"""
        if not ES_AVAILABLE:
            logger.error("Elasticsearch客户端不可用")
            return
        
        try:
            self.client = Elasticsearch([self.es_url])
            
            # 测试连接
            if self.client.ping():
                cluster_info = self.client.info()
                logger.info(f"Elasticsearch连接成功，版本: {cluster_info['version']['number']}")
            else:
                logger.error("Elasticsearch连接失败")
                self.client = None
                
        except Exception as e:
            logger.error(f"Elasticsearch客户端初始化失败: {str(e)}")
            self.client = None
    
    def _get_default_index_settings(self) -> Dict[str, Any]:
        """获取默认索引设置 - 使用标准分析器替代IK分析器"""
        return {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "max_result_window": 50000,
            "analysis": {
                "analyzer": {
                    "standard_analyzer": {
                        "type": "standard"
                    },
                    "financial_analyzer": {
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "financial_synonym",
                            "financial_stopwords"
                        ]
                    },
                    "search_analyzer": {
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "financial_synonym"
                        ]
                    }
                },
                "filter": {
                    "financial_synonym": {
                        "type": "synonym",
                        "synonyms": [
                            "股票,证券,equity",
                            "债券,bond",
                            "基金,fund",
                            "期货,futures",
                            "外汇,forex,fx",
                            "A股,沪深股市",
                            "港股,恒生指数",
                            "美股,纳斯达克,道琼斯",
                            "涨停,涨停板,daily_limit_up",
                            "跌停,跌停板,daily_limit_down",
                            "买入,做多,long",
                            "卖出,做空,short",
                            "市盈率,PE,P/E",
                            "市净率,PB,P/B",
                            "净资产收益率,ROE",
                            "每股收益,EPS",
                            "毛利率,gross_margin",
                            "净利率,net_margin"
                        ]
                    },
                    "financial_stopwords": {
                        "type": "stop",
                        "stopwords": [
                            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", 
                            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
                            "股票", "公司", "市场", "投资", "今日", "昨日", "本周", "上周"
                        ]
                    }
                }
            }
        }
    
    def _get_default_index_mappings(self) -> Dict[str, Any]:
        """获取默认索引映射"""
        return {
            "properties": {
                # 基础字段
                "title": {
                    "type": "text",
                    "analyzer": "financial_analyzer",
                    "search_analyzer": "search_analyzer",
                    "fields": {
                        "raw": {
                            "type": "keyword"
                        },
                        "suggest": {
                            "type": "completion"
                        }
                    }
                },
                "content": {
                    "type": "text",
                    "analyzer": "financial_analyzer",
                    "search_analyzer": "search_analyzer"
                },
                "summary": {
                    "type": "text",
                    "analyzer": "standard_analyzer"
                },
                "url": {
                    "type": "keyword",
                    "index": False
                },
                "source": {
                    "type": "keyword"
                },
                
                # 分类字段
                "news_type": {
                    "type": "keyword"
                },
                "industry": {
                    "type": "keyword"
                },
                "importance_level": {
                    "type": "keyword"
                },
                "investment_relevance": {
                    "type": "keyword"
                },
                
                # NLP处理结果
                "keywords": {
                    "type": "keyword"
                },
                "entities": {
                    "type": "nested",
                    "properties": {
                        "text": {
                            "type": "keyword"
                        },
                        "type": {
                            "type": "keyword"
                        },
                        "confidence": {
                            "type": "float"
                        },
                        "start": {
                            "type": "integer"
                        },
                        "end": {
                            "type": "integer"
                        }
                    }
                },
                
                # 情感分析
                "sentiment_label": {
                    "type": "keyword"
                },
                "sentiment_score": {
                    "type": "float"
                },
                "sentiment_confidence": {
                    "type": "float"
                },
                
                # 时间字段
                "publish_time": {
                    "type": "date",
                    "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                },
                "crawl_time": {
                    "type": "date",
                    "format": "yyyy-MM-dd HH:mm:ss||epoch_millis"
                },
                "index_time": {
                    "type": "date"
                },
                
                # 统计字段
                "word_count": {
                    "type": "integer"
                },
                "char_count": {
                    "type": "integer"
                },
                "reading_time": {
                    "type": "integer"
                },
                "importance_score": {
                    "type": "float"
                },
                
                # 去重和版本控制
                "content_hash": {
                    "type": "keyword"
                },
                "version": {
                    "type": "integer"
                },
                
                # 向量相关
                "vector_id": {
                    "type": "keyword"
                },
                
                # 地理位置（如果需要）
                "location": {
                    "type": "geo_point"
                },
                
                # 标签和分类
                "tags": {
                    "type": "keyword"
                },
                "categories": {
                    "type": "keyword"
                },
                
                # 质量评估
                "quality_score": {
                    "type": "float"
                },
                "quality_label": {
                    "type": "keyword"
                },
                
                # 用户交互
                "view_count": {
                    "type": "integer"
                },
                "like_count": {
                    "type": "integer"
                },
                "comment_count": {
                    "type": "integer"
                }
            }
        }
    
    def create_index(self, 
                    index_name: str,
                    settings: Dict[str, Any] = None,
                    mappings: Dict[str, Any] = None,
                    force_recreate: bool = False) -> bool:
        """
        创建索引
        
        Args:
            index_name: 索引名称
            settings: 索引设置
            mappings: 索引映射
            force_recreate: 是否强制重新创建
            
        Returns:
            创建是否成功
        """
        if not self.client:
            logger.error("Elasticsearch客户端不可用")
            return False
        
        try:
            # 检查索引是否存在
            if self.client.indices.exists(index=index_name):
                if force_recreate:
                    logger.info(f"删除现有索引: {index_name}")
                    self.client.indices.delete(index=index_name)
                else:
                    logger.info(f"索引 {index_name} 已存在")
                    return True
            
            # 使用提供的设置或默认设置
            index_settings = settings or self.index_settings
            index_mappings = mappings or self.index_mappings
            
            # 创建索引
            index_body = {
                "settings": index_settings,
                "mappings": index_mappings
            }
            
            self.client.indices.create(
                index=index_name,
                body=index_body
            )
            
            logger.info(f"索引 {index_name} 创建成功")
            return True
            
        except Exception as e:
            logger.error(f"索引创建失败: {str(e)}")
            return False
    
    def delete_index(self, index_name: str) -> bool:
        """删除索引"""
        if not self.client:
            return False
        
        try:
            if self.client.indices.exists(index=index_name):
                self.client.indices.delete(index=index_name)
                logger.info(f"索引 {index_name} 删除成功")
                return True
            else:
                logger.warning(f"索引 {index_name} 不存在")
                return False
                
        except Exception as e:
            logger.error(f"索引删除失败: {str(e)}")
            return False
    
    def create_index_template(self, 
                            template_name: str,
                            index_patterns: List[str],
                            settings: Dict[str, Any] = None,
                            mappings: Dict[str, Any] = None,
                            priority: int = 100) -> bool:
        """
        创建索引模板
        
        Args:
            template_name: 模板名称
            index_patterns: 索引模式列表
            settings: 索引设置
            mappings: 索引映射
            priority: 模板优先级
            
        Returns:
            创建是否成功
        """
        if not self.client:
            return False
        
        try:
            template_body = {
                "index_patterns": index_patterns,
                "priority": priority,
                "template": {
                    "settings": settings or self.index_settings,
                    "mappings": mappings or self.index_mappings
                },
                "_meta": {
                    "description": f"投资情报搜索引擎索引模板 - {template_name}",
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0.0"
                }
            }
            
            self.client.indices.put_index_template(
                name=template_name,
                body=template_body
            )
            
            logger.info(f"索引模板 {template_name} 创建成功")
            return True
            
        except Exception as e:
            logger.error(f"索引模板创建失败: {str(e)}")
            return False
    
    def update_index_mapping(self, 
                           index_name: str,
                           mapping_updates: Dict[str, Any]) -> bool:
        """
        更新索引映射
        
        Args:
            index_name: 索引名称
            mapping_updates: 映射更新
            
        Returns:
            更新是否成功
        """
        if not self.client:
            return False
        
        try:
            self.client.indices.put_mapping(
                index=index_name,
                body=mapping_updates
            )
            
            logger.info(f"索引 {index_name} 映射更新成功")
            return True
            
        except Exception as e:
            logger.error(f"索引映射更新失败: {str(e)}")
            return False
    
    def create_alias(self, 
                    alias_name: str,
                    index_names: List[str],
                    filters: Dict[str, Any] = None) -> bool:
        """
        创建索引别名
        
        Args:
            alias_name: 别名
            index_names: 索引名称列表
            filters: 过滤条件
            
        Returns:
            创建是否成功
        """
        if not self.client:
            return False
        
        try:
            actions = []
            
            for index_name in index_names:
                action = {
                    "add": {
                        "index": index_name,
                        "alias": alias_name
                    }
                }
                
                if filters:
                    action["add"]["filter"] = filters
                
                actions.append(action)
            
            self.client.indices.update_aliases(
                body={"actions": actions}
            )
            
            logger.info(f"别名 {alias_name} 创建成功")
            return True
            
        except Exception as e:
            logger.error(f"别名创建失败: {str(e)}")
            return False
    
    def get_index_info(self, index_name: str) -> Dict[str, Any]:
        """获取索引信息"""
        if not self.client:
            return {}
        
        try:
            # 获取索引设置
            settings = self.client.indices.get_settings(index=index_name)
            
            # 获取索引映射
            mappings = self.client.indices.get_mapping(index=index_name)
            
            # 获取索引统计
            stats = self.client.indices.stats(index=index_name)
            
            return {
                "settings": settings,
                "mappings": mappings,
                "stats": stats,
                "exists": True
            }
            
        except NotFoundError:
            return {"exists": False}
        except Exception as e:
            logger.error(f"获取索引信息失败: {str(e)}")
            return {"error": str(e)}
    
    def list_indices(self, pattern: str = None) -> List[str]:
        """列出索引"""
        if not self.client:
            return []
        
        try:
            if pattern:
                indices = self.client.indices.get(index=pattern)
            else:
                indices = self.client.indices.get_alias()
            
            return list(indices.keys())
            
        except Exception as e:
            logger.error(f"列出索引失败: {str(e)}")
            return []
    
    def optimize_index(self, index_name: str) -> bool:
        """优化索引"""
        if not self.client:
            return False
        
        try:
            # 强制合并段
            self.client.indices.forcemerge(
                index=index_name,
                max_num_segments=1
            )
            
            # 刷新索引
            self.client.indices.refresh(index=index_name)
            
            logger.info(f"索引 {index_name} 优化完成")
            return True
            
        except Exception as e:
            logger.error(f"索引优化失败: {str(e)}")
            return False
    
    def create_standard_indices(self) -> Dict[str, bool]:
        """创建标准索引"""
        results = {}
        
        # 新闻索引
        news_index = config.es_news_index
        results[news_index] = self.create_index(
            index_name=news_index,
            settings=self.index_settings,
            mappings=self.index_mappings
        )
        
        # 公告索引
        announcements_index = config.es_announcements_index
        results[announcements_index] = self.create_index(
            index_name=announcements_index,
            settings=self.index_settings,
            mappings=self.index_mappings
        )
        
        # 创建通用模板
        template_created = self.create_index_template(
            template_name="qsou_template",
            index_patterns=[f"{config.es_index_prefix}_*"],
            settings=self.index_settings,
            mappings=self.index_mappings
        )
        
        results["template"] = template_created
        
        return results
    
    def get_cluster_health(self) -> Dict[str, Any]:
        """获取集群健康状态"""
        if not self.client:
            return {"status": "unavailable"}
        
        try:
            health = self.client.cluster.health()
            return health
            
        except Exception as e:
            logger.error(f"获取集群健康状态失败: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def backup_index_settings(self, index_name: str, backup_path: str) -> bool:
        """备份索引设置"""
        try:
            index_info = self.get_index_info(index_name)
            
            if not index_info.get("exists"):
                logger.error(f"索引 {index_name} 不存在")
                return False
            
            backup_data = {
                "index_name": index_name,
                "settings": index_info["settings"],
                "mappings": index_info["mappings"],
                "backup_time": datetime.now().isoformat()
            }
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"索引设置已备份到: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"索引设置备份失败: {str(e)}")
            return False
    
    def restore_index_from_backup(self, backup_path: str, new_index_name: str = None) -> bool:
        """从备份恢复索引"""
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            index_name = new_index_name or backup_data["index_name"]
            settings = backup_data["settings"]
            mappings = backup_data["mappings"]
            
            # 提取实际的设置和映射
            if index_name in settings:
                actual_settings = settings[index_name]["settings"]
            else:
                actual_settings = settings
            
            if index_name in mappings:
                actual_mappings = mappings[index_name]["mappings"]
            else:
                actual_mappings = mappings
            
            return self.create_index(
                index_name=index_name,
                settings=actual_settings,
                mappings=actual_mappings,
                force_recreate=True
            )
            
        except Exception as e:
            logger.error(f"从备份恢复索引失败: {str(e)}")
            return False
