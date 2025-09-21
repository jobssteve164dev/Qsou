"""
Elasticsearch服务管理器
负责Elasticsearch连接、索引管理和全文搜索功能
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class ElasticsearchService:
    """Elasticsearch服务管理器"""
    
    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
        self.is_connected = False
        
    async def connect(self) -> bool:
        """连接到Elasticsearch"""
        try:
            self.client = AsyncElasticsearch(
                hosts=[{
                    'host': settings.ELASTICSEARCH_HOST,
                    'port': settings.ELASTICSEARCH_PORT,
                    'scheme': 'http'
                }],
                max_retries=1,  # 减少重试次数
                retry_on_timeout=False,  # 禁用超时重试
                verify_certs=False if settings.SKIP_SSL_VERIFY else True,
                # 添加连接池配置
                maxsize=10,
                # 只使用request_timeout，移除timeout参数
                request_timeout=30
            )
            
            # 测试连接
            info = await self.client.info()
            self.is_connected = True
            
            logger.info(
                "Elasticsearch连接成功",
                cluster_name=info.get('cluster_name'),
                version=info.get('version', {}).get('number')
            )
            
            # 确保索引存在
            await self._ensure_indices_exist()
            
            return True
            
        except Exception as e:
            logger.error("Elasticsearch连接失败", error=str(e))
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """断开Elasticsearch连接"""
        if self.client:
            await self.client.close()
            self.is_connected = False
            logger.info("Elasticsearch连接已断开")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查
        限制ES健康查询耗时，避免阻塞整体统计。
        """
        if not self.client or not self.is_connected:
            return {"status": "disconnected", "error": "No connection"}
        
        try:
            import asyncio
            # 优先使用 ping（HEAD /），最快速判断连通性
            ok = await asyncio.wait_for(self.client.ping(), timeout=1.5)
            if ok:
                # 轻量化：不再阻塞性地获取 cluster health，避免Windows本地耗时过长
                return {
                    "status": "connected",
                    "cluster_status": "unknown",
                }
            # ping 失败则再尝试一次短超时的 cluster health，以便返回更具体错误
            health = await asyncio.wait_for(self.client.cluster.health(), timeout=2.0)
            return {
                "status": "connected" if health else "error",
                "cluster_status": health.get('status') if isinstance(health, dict) else "unknown",
            }
        except asyncio.TimeoutError:
            return {"status": "timeout"}
        except Exception as e:
            logger.error("Elasticsearch健康检查失败", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def search_documents(
        self,
        query: str,
        index_name: Optional[str] = None,
        filters: Optional[Dict] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "relevance"
    ) -> Dict[str, Any]:
        """执行全文搜索"""
        if not self.client or not self.is_connected:
            raise ConnectionError("Elasticsearch未连接")
        
        index_name = index_name or f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
        
        # 构建搜索查询
        search_body = self._build_search_query(
            query=query,
            filters=filters,
            sort_by=sort_by
        )
        
        # 计算分页参数
        from_param = (page - 1) * page_size
        
        try:
            start_time = datetime.now()
            
            response = await self.client.search(
                index=index_name,
                body=search_body,
                from_=from_param,
                size=page_size,
                timeout='10s'  # 减少搜索超时时间
            )
            
            search_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # 解析搜索结果
            results = self._parse_search_results(response)
            
            logger.info(
                "Elasticsearch搜索完成",
                query=query,
                total_hits=response['hits']['total']['value'],
                search_time_ms=search_time,
                page=page,
                page_size=page_size,
                sort_by=sort_by
            )
            
            return {
                "total_count": response['hits']['total']['value'],
                "results": results,
                "search_time_ms": search_time,
                "aggregations": response.get('aggregations', {})
            }
            
        except Exception as e:
            logger.error("Elasticsearch搜索失败", query=query, page=page, page_size=page_size, error=str(e))
            raise
    
    async def get_suggestions(self, query: str, size: int = 5) -> List[str]:
        """获取搜索建议"""
        if not self.client or not self.is_connected:
            return []
        
        index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
        
        try:
            # 使用completion suggester
            suggest_body = {
                "suggest": {
                    "title_suggest": {
                        "prefix": query,
                        "completion": {
                            "field": "title_suggest",
                            "size": size
                        }
                    }
                }
            }
            
            response = await self.client.search(
                index=index_name,
                body=suggest_body
            )
            
            suggestions = []
            for option in response.get('suggest', {}).get('title_suggest', [{}])[0].get('options', []):
                suggestions.append(option['text'])
            
            return suggestions
            
        except Exception as e:
            logger.error("获取搜索建议失败", query=query, error=str(e))
            return []
    
    def _build_search_query(
        self,
        query: str,
        filters: Optional[Dict] = None,
        sort_by: str = "relevance"
    ) -> Dict[str, Any]:
        """构建Elasticsearch查询"""
        
        # 基础多字段查询
        query_body = {
            "multi_match": {
                "query": query,
                "fields": [
                    "title^3",      # 标题权重最高
                    "content^2",    # 内容权重中等
                    "tags^1.5",     # 标签权重较高
                    "summary"       # 摘要权重正常
                ],
                "type": "best_fields",
                "fuzziness": "AUTO"
            }
        }
        
        # 添加过滤器
        must_clauses = [query_body]
        filter_clauses = []
        
        if filters:
            if "source" in filters:
                filter_clauses.append({"term": {"source": filters["source"]}})
            
            if "date_range" in filters:
                date_range = filters["date_range"]
                filter_clauses.append({
                    "range": {
                        "published_at": {
                            "gte": date_range.get("start"),
                            "lte": date_range.get("end")
                        }
                    }
                })
            
            if "tags" in filters:
                filter_clauses.append({"terms": {"tags": filters["tags"]}})
        
        # 构建完整查询
        search_body = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses
                }
            },
            "highlight": {
                "fields": {
                    "title": {"pre_tags": ["<mark>"], "post_tags": ["</mark>"]},
                    "content": {"pre_tags": ["<mark>"], "post_tags": ["</mark>"]}
                }
            },
            "aggregations": {
                "sources": {"terms": {"field": "source", "size": 10}},
                "tags": {"terms": {"field": "tags", "size": 20}}
            }
        }
        
        # 添加排序
        if sort_by == "time":
            search_body["sort"] = [{"published_at": {"order": "desc"}}]
        elif sort_by == "popularity":
            search_body["sort"] = [{"view_count": {"order": "desc"}}]
        # relevance排序是默认的，不需要显式指定
        
        return search_body
    
    def _parse_search_results(self, response: Dict) -> List[Dict[str, Any]]:
        """解析Elasticsearch搜索结果"""
        results = []
        
        for hit in response['hits']['hits']:
            source = hit['_source']
            
            # 提取高亮内容
            highlight = hit.get('highlight', {})
            highlighted_title = highlight.get('title', [source.get('title', '')])[0]
            highlighted_content = highlight.get('content', [source.get('content', '')])[0]
            
            result = {
                "id": hit['_id'],
                "title": highlighted_title,
                "content": highlighted_content[:500] + "..." if len(highlighted_content) > 500 else highlighted_content,
                "source": source.get('source', ''),
                "url": source.get('url'),
                "published_at": source.get('published_at'),
                "relevance_score": hit['_score'] / 10.0,  # 归一化到0-1
                "tags": source.get('tags', [])
            }
            
            results.append(result)
        
        return results
    
    async def _ensure_indices_exist(self):
        """确保必要的索引存在"""
        index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
        
        try:
            exists = await self.client.indices.exists(index=index_name)
            
            if not exists:
                # 创建索引映射 - 使用标准分析器替代IK分析器
                mapping = {
                    "mappings": {
                        "properties": {
                            "title": {
                                "type": "text",
                                "analyzer": "standard",
                                "search_analyzer": "standard"
                            },
                            "content": {
                                "type": "text",
                                "analyzer": "standard",
                                "search_analyzer": "standard"
                            },
                            "summary": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "source": {"type": "keyword"},
                            "url": {"type": "keyword"},
                            "published_at": {"type": "date"},
                            "tags": {"type": "keyword"},
                            "view_count": {"type": "integer"},
                            "title_suggest": {
                                "type": "completion",
                                "analyzer": "standard"
                            }
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                }
                
                await self.client.indices.create(index=index_name, body=mapping)
                logger.info(f"创建Elasticsearch索引: {index_name}")
                
        except Exception as e:
            logger.error("创建Elasticsearch索引失败", error=str(e))
            raise


# 全局Elasticsearch服务实例
elasticsearch_service = ElasticsearchService()
