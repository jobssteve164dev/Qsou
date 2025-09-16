from __future__ import annotations
"""
Elasticsearch搜索引擎

提供高级搜索功能：
- 全文搜索
- 聚合查询
- 复合查询
- 搜索建议
- 搜索结果排序和高亮
"""
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from datetime import datetime, timedelta
import re

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.exceptions import RequestError, NotFoundError
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False
    logger.warning("elasticsearch未安装，搜索引擎功能不可用")

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import config


class SearchEngine:
    """Elasticsearch搜索引擎"""
    
    def __init__(self, 
                 es_client: Elasticsearch = None,
                 default_index: str = None):
        """
        初始化搜索引擎
        
        Args:
            es_client: Elasticsearch客户端
            default_index: 默认索引名称
        """
        self.client = es_client
        self.default_index = default_index or config.es_news_index
        
        # 搜索配置
        self.default_size = 10
        self.max_size = 100
        self.default_timeout = "30s"
        
        # 搜索统计
        self.search_stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'total_search_time': 0.0
        }
        
        logger.info("Elasticsearch搜索引擎初始化完成")
    
    def search(self,
               query: str,
               index_name: str = None,
               size: int = None,
               from_: int = 0,
               sort: List[Dict[str, Any]] = None,
               filters: Dict[str, Any] = None,
               highlight: bool = True,
               **kwargs) -> Dict[str, Any]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            index_name: 索引名称
            size: 返回结果数量
            from_: 起始位置
            sort: 排序规则
            filters: 过滤条件
            highlight: 是否高亮
            **kwargs: 其他搜索参数
            
        Returns:
            搜索结果
        """
        if not self.client:
            return self._create_error_result("Elasticsearch客户端不可用")
        
        if not query:
            return self._create_empty_result()
        
        start_time = datetime.now()
        index_name = index_name or self.default_index
        size = min(size or self.default_size, self.max_size)
        
        try:
            self.search_stats['total_searches'] += 1
            
            # 构建搜索体
            search_body = self._build_search_body(
                query=query,
                size=size,
                from_=from_,
                sort=sort,
                filters=filters,
                highlight=highlight,
                **kwargs
            )
            
            # 执行搜索
            response = self.client.search(
                index=index_name,
                body=search_body,
                timeout=self.default_timeout
            )
            
            # 处理搜索结果
            result = self._process_search_response(response, query, start_time)
            
            self.search_stats['successful_searches'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"搜索执行失败: {str(e)}")
            self.search_stats['failed_searches'] += 1
            return self._create_error_result(str(e))
    
    def _build_search_body(self,
                          query: str,
                          size: int,
                          from_: int,
                          sort: List[Dict[str, Any]] = None,
                          filters: Dict[str, Any] = None,
                          highlight: bool = True,
                          **kwargs) -> Dict[str, Any]:
        """构建搜索体"""
        
        # 构建查询
        search_query = self._build_query(query, filters, **kwargs)
        
        # 构建搜索体
        search_body = {
            "query": search_query,
            "size": size,
            "from": from_,
            "_source": {
                "excludes": ["content"]  # 默认不返回全文内容
            }
        }
        
        # 添加排序
        if sort:
            search_body["sort"] = sort
        else:
            # 默认排序：相关性 + 时间
            search_body["sort"] = [
                {"_score": {"order": "desc"}},
                {"publish_time": {"order": "desc", "missing": "_last"}}
            ]
        
        # 添加高亮
        if highlight:
            search_body["highlight"] = self._build_highlight_config()
        
        # 添加聚合
        if kwargs.get('include_aggregations', False):
            search_body["aggs"] = self._build_aggregations()
        
        return search_body
    
    def _build_query(self, 
                    query: str,
                    filters: Dict[str, Any] = None,
                    **kwargs) -> Dict[str, Any]:
        """构建查询"""
        
        # 主查询
        main_query = {
            "bool": {
                "should": [
                    # 标题匹配（权重最高）
                    {
                        "match": {
                            "title": {
                                "query": query,
                                "boost": 3.0,
                                "analyzer": "search_analyzer"
                            }
                        }
                    },
                    # 内容匹配
                    {
                        "match": {
                            "content": {
                                "query": query,
                                "boost": 1.0,
                                "analyzer": "search_analyzer"
                            }
                        }
                    },
                    # 摘要匹配
                    {
                        "match": {
                            "summary": {
                                "query": query,
                                "boost": 2.0
                            }
                        }
                    },
                    # 关键词匹配
                    {
                        "terms": {
                            "keywords": query.split(),
                            "boost": 2.5
                        }
                    },
                    # 实体匹配
                    {
                        "nested": {
                            "path": "entities",
                            "query": {
                                "match": {
                                    "entities.text": {
                                        "query": query,
                                        "boost": 2.0
                                    }
                                }
                            }
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }
        
        # 添加过滤条件
        if filters:
            filter_clauses = []
            
            for field, value in filters.items():
                if field == "date_range":
                    # 日期范围过滤
                    date_filter = self._build_date_filter(value)
                    if date_filter:
                        filter_clauses.append(date_filter)
                
                elif field == "source":
                    # 来源过滤
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {"source": value}})
                    else:
                        filter_clauses.append({"term": {"source": value}})
                
                elif field == "news_type":
                    # 新闻类型过滤
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {"news_type": value}})
                    else:
                        filter_clauses.append({"term": {"news_type": value}})
                
                elif field == "industry":
                    # 行业过滤
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {"industry": value}})
                    else:
                        filter_clauses.append({"term": {"industry": value}})
                
                elif field == "importance_level":
                    # 重要性级别过滤
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {"importance_level": value}})
                    else:
                        filter_clauses.append({"term": {"importance_level": value}})
                
                elif field == "sentiment":
                    # 情感过滤
                    if isinstance(value, list):
                        filter_clauses.append({"terms": {"sentiment_label": value}})
                    else:
                        filter_clauses.append({"term": {"sentiment_label": value}})
                
                elif field == "score_range":
                    # 分数范围过滤
                    if "min" in value or "max" in value:
                        range_filter = {"range": {"importance_score": {}}}
                        if "min" in value:
                            range_filter["range"]["importance_score"]["gte"] = value["min"]
                        if "max" in value:
                            range_filter["range"]["importance_score"]["lte"] = value["max"]
                        filter_clauses.append(range_filter)
            
            if filter_clauses:
                if "bool" not in main_query:
                    main_query = {"bool": {"must": [main_query]}}
                main_query["bool"]["filter"] = filter_clauses
        
        return main_query
    
    def _build_date_filter(self, date_range: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """构建日期过滤器"""
        if not date_range:
            return None
        
        range_filter = {"range": {"publish_time": {}}}
        
        if "start" in date_range:
            range_filter["range"]["publish_time"]["gte"] = date_range["start"]
        
        if "end" in date_range:
            range_filter["range"]["publish_time"]["lte"] = date_range["end"]
        
        # 预设时间范围
        if "preset" in date_range:
            preset = date_range["preset"]
            now = datetime.now()
            
            if preset == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                range_filter["range"]["publish_time"]["gte"] = start_date
            elif preset == "week":
                start_date = now - timedelta(days=7)
                range_filter["range"]["publish_time"]["gte"] = start_date
            elif preset == "month":
                start_date = now - timedelta(days=30)
                range_filter["range"]["publish_time"]["gte"] = start_date
            elif preset == "year":
                start_date = now - timedelta(days=365)
                range_filter["range"]["publish_time"]["gte"] = start_date
        
        return range_filter if range_filter["range"]["publish_time"] else None
    
    def _build_highlight_config(self) -> Dict[str, Any]:
        """构建高亮配置"""
        return {
            "fields": {
                "title": {
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                    "fragment_size": 150,
                    "number_of_fragments": 1
                },
                "content": {
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                    "fragment_size": 150,
                    "number_of_fragments": 3
                },
                "summary": {
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"],
                    "fragment_size": 100,
                    "number_of_fragments": 1
                }
            }
        }
    
    def _build_aggregations(self) -> Dict[str, Any]:
        """构建聚合查询"""
        return {
            "news_types": {
                "terms": {
                    "field": "news_type",
                    "size": 10
                }
            },
            "industries": {
                "terms": {
                    "field": "industry",
                    "size": 15
                }
            },
            "sources": {
                "terms": {
                    "field": "source",
                    "size": 20
                }
            },
            "sentiment_distribution": {
                "terms": {
                    "field": "sentiment_label",
                    "size": 5
                }
            },
            "importance_levels": {
                "terms": {
                    "field": "importance_level",
                    "size": 5
                }
            },
            "publish_time_histogram": {
                "date_histogram": {
                    "field": "publish_time",
                    "calendar_interval": "day",
                    "min_doc_count": 1
                }
            }
        }
    
    def _process_search_response(self, 
                               response: Dict[str, Any],
                               query: str,
                               start_time: datetime) -> Dict[str, Any]:
        """处理搜索响应"""
        
        end_time = datetime.now()
        search_time = (end_time - start_time).total_seconds()
        self.search_stats['total_search_time'] += search_time
        
        # 提取基本信息
        hits = response.get('hits', {})
        total = hits.get('total', {})
        
        if isinstance(total, dict):
            total_count = total.get('value', 0)
            total_relation = total.get('relation', 'eq')
        else:
            total_count = total
            total_relation = 'eq'
        
        # 处理文档
        documents = []
        for hit in hits.get('hits', []):
            doc = {
                'id': hit['_id'],
                'score': hit['_score'],
                'source': hit['_source']
            }
            
            # 添加高亮
            if 'highlight' in hit:
                doc['highlight'] = hit['highlight']
            
            documents.append(doc)
        
        # 处理聚合结果
        aggregations = {}
        if 'aggregations' in response:
            aggregations = self._process_aggregations(response['aggregations'])
        
        result = {
            'success': True,
            'query': query,
            'total': total_count,
            'total_relation': total_relation,
            'documents': documents,
            'aggregations': aggregations,
            'took': response.get('took', 0),
            'search_time': search_time,
            'timed_out': response.get('timed_out', False),
            'max_score': hits.get('max_score', 0.0)
        }
        
        return result
    
    def _process_aggregations(self, aggs: Dict[str, Any]) -> Dict[str, Any]:
        """处理聚合结果"""
        processed_aggs = {}
        
        for agg_name, agg_data in aggs.items():
            if 'buckets' in agg_data:
                # 处理桶聚合
                processed_aggs[agg_name] = [
                    {
                        'key': bucket['key'],
                        'doc_count': bucket['doc_count']
                    }
                    for bucket in agg_data['buckets']
                ]
            elif 'value' in agg_data:
                # 处理度量聚合
                processed_aggs[agg_name] = agg_data['value']
        
        return processed_aggs
    
    def suggest(self,
                text: str,
                index_name: str = None,
                size: int = 5) -> List[str]:
        """
        搜索建议
        
        Args:
            text: 输入文本
            index_name: 索引名称
            size: 建议数量
            
        Returns:
            建议列表
        """
        if not self.client or not text:
            return []
        
        index_name = index_name or self.default_index
        
        try:
            # 使用completion suggester
            suggest_body = {
                "title_suggest": {
                    "prefix": text,
                    "completion": {
                        "field": "title.suggest",
                        "size": size
                    }
                }
            }
            
            response = self.client.search(
                index=index_name,
                body={"suggest": suggest_body}
            )
            
            suggestions = []
            if 'suggest' in response and 'title_suggest' in response['suggest']:
                for suggest_result in response['suggest']['title_suggest']:
                    for option in suggest_result.get('options', []):
                        suggestions.append(option['text'])
            
            return suggestions[:size]
            
        except Exception as e:
            logger.error(f"搜索建议失败: {str(e)}")
            return []
    
    def more_like_this(self,
                      document_id: str,
                      index_name: str = None,
                      size: int = 5) -> Dict[str, Any]:
        """
        查找相似文档
        
        Args:
            document_id: 文档ID
            index_name: 索引名称
            size: 返回数量
            
        Returns:
            相似文档
        """
        if not self.client:
            return self._create_error_result("客户端不可用")
        
        index_name = index_name or self.default_index
        
        try:
            mlt_query = {
                "more_like_this": {
                    "fields": ["title", "content", "summary"],
                    "like": [
                        {
                            "_index": index_name,
                            "_id": document_id
                        }
                    ],
                    "min_term_freq": 1,
                    "max_query_terms": 12,
                    "min_doc_freq": 1
                }
            }
            
            search_body = {
                "query": mlt_query,
                "size": size,
                "_source": {
                    "excludes": ["content"]
                }
            }
            
            response = self.client.search(
                index=index_name,
                body=search_body
            )
            
            return self._process_search_response(response, f"similar_to:{document_id}", datetime.now())
            
        except Exception as e:
            logger.error(f"相似文档查询失败: {str(e)}")
            return self._create_error_result(str(e))
    
    def advanced_search(self,
                       search_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        高级搜索
        
        Args:
            search_params: 搜索参数
            
        Returns:
            搜索结果
        """
        # 提取参数
        query = search_params.get('query', '')
        title_query = search_params.get('title_query', '')
        content_query = search_params.get('content_query', '')
        exact_phrase = search_params.get('exact_phrase', '')
        exclude_words = search_params.get('exclude_words', '')
        
        # 构建复合查询
        must_clauses = []
        must_not_clauses = []
        
        # 主查询
        if query:
            must_clauses.append({
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content", "summary^2"],
                    "type": "best_fields"
                }
            })
        
        # 标题查询
        if title_query:
            must_clauses.append({
                "match": {
                    "title": {
                        "query": title_query,
                        "boost": 2.0
                    }
                }
            })
        
        # 内容查询
        if content_query:
            must_clauses.append({
                "match": {
                    "content": content_query
                }
            })
        
        # 精确短语
        if exact_phrase:
            must_clauses.append({
                "multi_match": {
                    "query": exact_phrase,
                    "fields": ["title", "content"],
                    "type": "phrase"
                }
            })
        
        # 排除词
        if exclude_words:
            exclude_terms = exclude_words.split()
            for term in exclude_terms:
                must_not_clauses.append({
                    "multi_match": {
                        "query": term,
                        "fields": ["title", "content"]
                    }
                })
        
        # 构建最终查询
        if not must_clauses:
            return self._create_empty_result()
        
        bool_query = {
            "bool": {
                "must": must_clauses
            }
        }
        
        if must_not_clauses:
            bool_query["bool"]["must_not"] = must_not_clauses
        
        # 执行搜索
        search_body = {
            "query": bool_query,
            "size": search_params.get('size', self.default_size),
            "from": search_params.get('from', 0)
        }
        
        try:
            response = self.client.search(
                index=search_params.get('index_name', self.default_index),
                body=search_body
            )
            
            return self._process_search_response(response, query, datetime.now())
            
        except Exception as e:
            logger.error(f"高级搜索失败: {str(e)}")
            return self._create_error_result(str(e))
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """创建空结果"""
        return {
            'success': True,
            'query': '',
            'total': 0,
            'documents': [],
            'aggregations': {},
            'took': 0,
            'search_time': 0.0,
            'timed_out': False,
            'max_score': 0.0
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            'success': False,
            'error': error_message,
            'query': '',
            'total': 0,
            'documents': [],
            'aggregations': {},
            'took': 0,
            'search_time': 0.0,
            'timed_out': False,
            'max_score': 0.0
        }
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索统计"""
        stats = self.search_stats.copy()
        
        # 计算平均搜索时间
        if stats['successful_searches'] > 0:
            stats['avg_search_time'] = stats['total_search_time'] / stats['successful_searches']
        else:
            stats['avg_search_time'] = 0.0
        
        # 计算成功率
        if stats['total_searches'] > 0:
            stats['success_rate'] = stats['successful_searches'] / stats['total_searches']
        else:
            stats['success_rate'] = 0.0
        
        return stats
