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
import copy

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
            # 首选配置的主机
            primary_host = settings.ELASTICSEARCH_HOST
            port = settings.ELASTICSEARCH_PORT
            async def _try_connect(host: str) -> bool:
                # 关闭旧client避免未关闭会话
                try:
                    if self.client:
                        await self.client.close()
                except Exception:
                    pass
                self.client = AsyncElasticsearch(
                    hosts=[{'host': host, 'port': port, 'scheme': 'http'}],
                    max_retries=1,
                    retry_on_timeout=False,
                    verify_certs=False if settings.SKIP_SSL_VERIFY else True,
                    maxsize=10,
                    request_timeout=5
                )
                info = await self.client.info()
                self.is_connected = True
                logger.info(
                    "Elasticsearch连接成功",
                    host=host,
                    cluster_name=info.get('cluster_name'),
                    version=info.get('version', {}).get('number')
                )
                await self._ensure_indices_exist()
                return True

            # 尝试主机
            try:
                return await _try_connect(primary_host)
            except Exception as e1:
                logger.error("Elasticsearch连接失败", error=str(e1), host=primary_host)
                # 回退到127.0.0.1，规避localhost/IPv6解析问题
                if primary_host != '127.0.0.1':
                    try:
                        return await _try_connect('127.0.0.1')
                    except Exception as e2:
                        logger.error("Elasticsearch备用主机连接失败", error=str(e2), host='127.0.0.1')
                self.is_connected = False
                return False
            
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
        # 观测优先：在关键路径输出状态
        if not self.client or not self.is_connected:
            logger.error(
                "Elasticsearch未连接",
                has_client=bool(self.client),
                is_connected=self.is_connected
            )
            # 轻量重连一次（非简化业务逻辑，只作为连接自愈）
            try:
                await self.connect()
            except Exception as e:
                raise ConnectionError("Elasticsearch未连接") from e
        
        index_name = index_name or f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
        
        # 构建搜索查询
        search_body = self._build_search_query(
            query=query,
            filters=filters,
            sort_by=sort_by
        )
        
        # 计算分页参数
        from datetime import datetime
        start_time = datetime.now()
        from elastic_transport import TransportError
        try:
            response = await self.client.search(
                index=index_name,
                body=search_body,
                from_=(page - 1) * page_size,
                size=page_size
            )
            search_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            results = self._parse_search_results(response)
            
            logger.info(
                "Elasticsearch搜索完成",
                index=index_name,
                query=query,
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
            logger.error(
                "Elasticsearch搜索失败",
                error=str(e),
                index=index_name,
                page=page,
                page_size=page_size,
                query=query
            )
            # 针对映射/fielddata问题的安全回退：移除聚合后重试一次
            msg = str(e)
            needs_agg_fallback = any(substr in msg for substr in [
                'Fielddata is disabled',
                'no mapping found for field',
                'search_phase_execution_exception'
            ])
            if needs_agg_fallback and isinstance(search_body, dict) and 'aggregations' in search_body:
                fallback_body = copy.deepcopy(search_body)
                fallback_body.pop('aggregations', None)
                try:
                    logger.warning("Elasticsearch回退查询：去除aggregations后重试", index=index_name)
                    response = await self.client.search(
                        index=index_name,
                        body=fallback_body,
                        from_=(page - 1) * page_size,
                        size=page_size
                    )
                    results = self._parse_search_results(response)
                    return {
                        "total_count": response['hits']['total']['value'],
                        "results": results,
                        "search_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                        "aggregations": response.get('aggregations', {})
                    }
                except Exception as e2:
                    logger.error("Elasticsearch回退查询失败", error=str(e2))
            
            # 针对连接/超时等错误，进行一次轻量重试
            try:
                response = await self.client.search(
                    index=index_name,
                    body=search_body,
                    from_=(page - 1) * page_size,
                    size=page_size
                )
                results = self._parse_search_results(response)
                return {
                    "total_count": response['hits']['total']['value'],
                    "results": results,
                    "search_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "aggregations": response.get('aggregations', {})
                }
            except Exception as e2:
                logger.error("Elasticsearch搜索重试失败", error=str(e2))
            # 将原始错误抛出，交由上层统一处理
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
            # 如果缺少completion字段，回退到title前缀检索
            if 'no mapping found for field [title_suggest]' in str(e):
                try:
                    fallback_body = {
                        "size": size,
                        "_source": ["title"],
                        "query": {
                            "match_phrase_prefix": {
                                "title": {
                                    "query": query
                                }
                            }
                        }
                    }
                    resp = await self.client.search(index=index_name, body=fallback_body)
                    hits = resp.get('hits', {}).get('hits', [])
                    titles = []
                    for h in hits:
                        t = h.get('_source', {}).get('title')
                        if t:
                            titles.append(t)
                    return titles[:size]
                except Exception as e2:
                    logger.error("建议回退查询失败", error=str(e2))
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
            search_body["sort"] = [
                {"publish_time": {"order": "desc", "unmapped_type": "date"}},
                {"published_at": {"order": "desc", "unmapped_type": "date"}},
            ]
        elif sort_by == "popularity":
            search_body["sort"] = [{"view_count": {"order": "desc"}}]
        # relevance排序是默认的，不需要显式指定
        
        return search_body
    
    def _parse_search_results(self, response: Dict) -> List[Dict[str, Any]]:
        """解析Elasticsearch搜索结果"""
        results = []
        
        hits_obj = response.get('hits', {})
        max_score = hits_obj.get('max_score') or 1.0
        if not max_score or max_score <= 0:
            max_score = 1.0
        for hit in hits_obj.get('hits', []):
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
                "relevance_score": min(1.0, float(hit.get('_score') or 0.0) / float(max_score)),
                "tags": source.get('tags', [])
            }
            
            results.append(result)
        
        return results
    
    async def _ensure_indices_exist(self):
        """确保必要的索引/别名存在并保持稳定

        规范：业务统一使用别名 <prefix>documents（如 qsou_documents）。
        - 若别名已存在，直接返回。
        - 若别名不存在：
            1) 若已存在形如 <alias>_* 的物理索引，则将别名指向其中一个（优先选择字典序最大的）。
            2) 若不存在任何相关索引，则创建 <alias>_v1 并建立映射，然后将别名指向它。
        """
        alias_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
        try:
            # 1) 别名已存在
            try:
                if await self.client.indices.exists_alias(name=alias_name):
                    return
            except Exception:
                # 某些版本在不存在时抛异常，统一按不存在处理
                pass

            # 2) 查找已有物理索引
            target_index = None
            try:
                existing = await self.client.indices.get(index=f"{alias_name}*")
                if isinstance(existing, dict) and existing:
                    # 过滤掉与别名同名的冲突（极少数情况下存在同名索引）
                    candidates = [k for k in existing.keys() if k != alias_name]
                    if candidates:
                        target_index = sorted(candidates)[-1]
            except Exception:
                # 没有任何匹配索引也属于正常场景
                target_index = None

            # 3) 如无可用索引则创建 _v1
            if not target_index:
                target_index = f"{alias_name}_v1"
                mapping = {
                    "mappings": {
                        "properties": {
                            "title": {"type": "text", "analyzer": "standard", "search_analyzer": "standard"},
                            "content": {"type": "text", "analyzer": "standard", "search_analyzer": "standard"},
                            "summary": {"type": "text", "analyzer": "standard"},
                            "source": {"type": "keyword"},
                            "url": {"type": "keyword"},
                            "publish_time": {"type": "date"},
                            "published_at": {"type": "date"},
                            "tags": {"type": "keyword"},
                            "view_count": {"type": "integer"},
                            "title_suggest": {"type": "completion", "analyzer": "standard"}
                        }
                    },
                    "settings": {"number_of_shards": 1, "number_of_replicas": 0}
                }
                # 如果索引已存在则跳过创建
                if not await self.client.indices.exists(index=target_index):
                    await self.client.indices.create(index=target_index, body=mapping)
                    logger.info("创建Elasticsearch索引", index=target_index)

            # 4) 绑定别名到物理索引
            await self.client.indices.put_alias(index=target_index, name=alias_name)
            logger.info("确保Elasticsearch别名完成", alias=alias_name, target=target_index)

        except Exception as e:
            logger.error("创建/绑定Elasticsearch别名失败", error=str(e))
            raise


# 全局Elasticsearch服务实例
elasticsearch_service = ElasticsearchService()
