"""
相似度搜索器

提供高级的相似度搜索功能：
- 语义搜索
- 混合搜索（向量+关键词）
- 多模态搜索
- 搜索结果排序和过滤
"""
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
from loguru import logger
from datetime import datetime, timedelta
import re

from .embeddings import TextEmbedder
from .vector_store import VectorStore


class SimilaritySearcher:
    """相似度搜索器"""
    
    def __init__(self, 
                 embedder: TextEmbedder,
                 vector_store: VectorStore):
        """
        初始化相似度搜索器
        
        Args:
            embedder: 文本向量化器
            vector_store: 向量存储器
        """
        self.embedder = embedder
        self.vector_store = vector_store
        
        # 搜索配置
        self.default_limit = 10
        self.default_score_threshold = 0.0
        self.max_limit = 100
        
        logger.info("相似度搜索器初始化完成")
    
    def semantic_search(self, 
                       query: str,
                       limit: int = None,
                       score_threshold: float = None,
                       filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            limit: 返回结果数量
            score_threshold: 相似度阈值
            filters: 过滤条件
            
        Returns:
            搜索结果列表
        """
        if not query or not isinstance(query, str):
            logger.warning("查询文本为空")
            return []
        
        limit = min(limit or self.default_limit, self.max_limit)
        score_threshold = score_threshold or self.default_score_threshold
        
        try:
            # 生成查询向量
            query_vector = self.embedder.embed_text(query)
            
            if np.all(query_vector == 0):
                logger.warning("查询向量为零向量")
                return []
            
            # 执行向量搜索
            results = self.vector_store.search_similar_vectors(
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                filter_conditions=filters
            )
            
            # 后处理结果
            processed_results = self._post_process_results(results, query)
            
            logger.info(f"语义搜索完成，查询: '{query[:50]}...', 返回 {len(processed_results)} 个结果")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"语义搜索失败: {str(e)}")
            return []
    
    def hybrid_search(self,
                     query: str,
                     limit: int = None,
                     vector_weight: float = 0.7,
                     keyword_weight: float = 0.3,
                     filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        混合搜索（向量搜索 + 关键词匹配）
        
        Args:
            query: 查询文本
            limit: 返回结果数量
            vector_weight: 向量搜索权重
            keyword_weight: 关键词匹配权重
            filters: 过滤条件
            
        Returns:
            搜索结果列表
        """
        if not query:
            return []
        
        limit = min(limit or self.default_limit, self.max_limit)
        
        try:
            # 1. 向量搜索
            vector_results = self.semantic_search(
                query=query,
                limit=limit * 2,  # 获取更多候选结果
                filters=filters
            )
            
            # 2. 关键词匹配
            keyword_results = self._keyword_search(query, vector_results)
            
            # 3. 合并和重新排序
            hybrid_results = self._merge_search_results(
                vector_results, 
                keyword_results,
                vector_weight,
                keyword_weight
            )
            
            # 4. 截取最终结果
            final_results = hybrid_results[:limit]
            
            logger.info(f"混合搜索完成，返回 {len(final_results)} 个结果")
            
            return final_results
            
        except Exception as e:
            logger.error(f"混合搜索失败: {str(e)}")
            return []
    
    def multi_query_search(self,
                          queries: List[str],
                          aggregation_method: str = "average",
                          limit: int = None,
                          filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        多查询搜索
        
        Args:
            queries: 查询文本列表
            aggregation_method: 聚合方法 ("average", "max", "weighted")
            limit: 返回结果数量
            filters: 过滤条件
            
        Returns:
            搜索结果列表
        """
        if not queries:
            return []
        
        limit = min(limit or self.default_limit, self.max_limit)
        
        try:
            # 生成所有查询的向量
            query_vectors = []
            for query in queries:
                if query and isinstance(query, str):
                    vector = self.embedder.embed_text(query)
                    if not np.all(vector == 0):
                        query_vectors.append(vector)
            
            if not query_vectors:
                logger.warning("没有有效的查询向量")
                return []
            
            # 聚合查询向量
            if aggregation_method == "average":
                aggregated_vector = np.mean(query_vectors, axis=0)
            elif aggregation_method == "max":
                aggregated_vector = np.max(query_vectors, axis=0)
            elif aggregation_method == "weighted":
                # 简单的权重：第一个查询权重最高
                weights = [1.0 / (i + 1) for i in range(len(query_vectors))]
                weights = np.array(weights) / sum(weights)
                aggregated_vector = np.average(query_vectors, axis=0, weights=weights)
            else:
                aggregated_vector = np.mean(query_vectors, axis=0)
            
            # 执行搜索
            results = self.vector_store.search_similar_vectors(
                query_vector=aggregated_vector,
                limit=limit,
                filter_conditions=filters
            )
            
            # 后处理
            processed_results = self._post_process_results(results, " ".join(queries))
            
            logger.info(f"多查询搜索完成，查询数: {len(queries)}, 返回 {len(processed_results)} 个结果")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"多查询搜索失败: {str(e)}")
            return []
    
    def find_similar_documents(self,
                             document_id: str,
                             limit: int = None,
                             exclude_self: bool = True,
                             filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        查找相似文档
        
        Args:
            document_id: 文档ID
            limit: 返回结果数量
            exclude_self: 是否排除自身
            filters: 过滤条件
            
        Returns:
            相似文档列表
        """
        limit = min(limit or self.default_limit, self.max_limit)
        
        try:
            # 获取目标文档的向量
            target_document = self.vector_store.get_vector_by_id(document_id)
            if not target_document:
                logger.error(f"文档 {document_id} 不存在")
                return []
            
            target_vector = np.array(target_document['vector'])
            
            # 搜索相似向量
            search_limit = limit + 1 if exclude_self else limit
            results = self.vector_store.search_similar_vectors(
                query_vector=target_vector,
                limit=search_limit,
                filter_conditions=filters
            )
            
            # 排除自身
            if exclude_self:
                results = [r for r in results if r['id'] != document_id]
            
            # 截取结果
            final_results = results[:limit]
            
            logger.info(f"相似文档搜索完成，目标文档: {document_id}, 返回 {len(final_results)} 个结果")
            
            return final_results
            
        except Exception as e:
            logger.error(f"相似文档搜索失败: {str(e)}")
            return []
    
    def search_by_filters(self,
                         filters: Dict[str, Any],
                         limit: int = None,
                         sort_by: str = None,
                         sort_order: str = "desc") -> List[Dict[str, Any]]:
        """
        基于过滤条件搜索
        
        Args:
            filters: 过滤条件
            limit: 返回结果数量
            sort_by: 排序字段
            sort_order: 排序顺序 ("asc", "desc")
            
        Returns:
            搜索结果列表
        """
        limit = min(limit or self.default_limit, self.max_limit)
        
        try:
            # 使用零向量进行搜索（主要依靠过滤器）
            zero_vector = np.zeros(self.vector_store.vector_dimension)
            
            results = self.vector_store.search_similar_vectors(
                query_vector=zero_vector,
                limit=limit * 2,  # 获取更多结果用于排序
                score_threshold=0.0,
                filter_conditions=filters
            )
            
            # 排序
            if sort_by and results:
                results = self._sort_results(results, sort_by, sort_order)
            
            # 截取结果
            final_results = results[:limit]
            
            logger.info(f"过滤搜索完成，过滤条件: {filters}, 返回 {len(final_results)} 个结果")
            
            return final_results
            
        except Exception as e:
            logger.error(f"过滤搜索失败: {str(e)}")
            return []
    
    def _keyword_search(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """在候选结果中进行关键词搜索"""
        if not query or not candidates:
            return []
        
        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        
        keyword_results = []
        
        for candidate in candidates:
            payload = candidate.get('payload', {})
            title = payload.get('title', '')
            content = payload.get('content', '')
            
            # 计算关键词匹配分数
            keyword_score = self._calculate_keyword_score(query_keywords, title, content)
            
            if keyword_score > 0:
                result = candidate.copy()
                result['keyword_score'] = keyword_score
                keyword_results.append(result)
        
        # 按关键词分数排序
        keyword_results.sort(key=lambda x: x['keyword_score'], reverse=True)
        
        return keyword_results
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        # 移除标点符号，分割单词
        cleaned_text = re.sub(r'[^\w\s]', ' ', text)
        words = cleaned_text.split()
        
        # 过滤短词和停用词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那'}
        keywords = [word for word in words if len(word) > 1 and word not in stopwords]
        
        return keywords
    
    def _calculate_keyword_score(self, query_keywords: List[str], title: str, content: str) -> float:
        """计算关键词匹配分数"""
        if not query_keywords:
            return 0.0
        
        title_lower = title.lower()
        content_lower = content.lower()
        
        score = 0.0
        
        for keyword in query_keywords:
            keyword_lower = keyword.lower()
            
            # 标题匹配权重更高
            title_matches = title_lower.count(keyword_lower)
            content_matches = content_lower.count(keyword_lower)
            
            score += title_matches * 2.0 + content_matches * 1.0
        
        # 归一化分数
        max_possible_score = len(query_keywords) * 3.0  # 假设每个关键词在标题中出现一次
        normalized_score = min(score / max_possible_score, 1.0) if max_possible_score > 0 else 0.0
        
        return normalized_score
    
    def _merge_search_results(self,
                            vector_results: List[Dict[str, Any]],
                            keyword_results: List[Dict[str, Any]],
                            vector_weight: float,
                            keyword_weight: float) -> List[Dict[str, Any]]:
        """合并向量搜索和关键词搜索结果"""
        # 创建结果字典，以ID为键
        merged_results = {}
        
        # 处理向量搜索结果
        for i, result in enumerate(vector_results):
            doc_id = result['id']
            vector_score = result['score']
            
            merged_results[doc_id] = result.copy()
            merged_results[doc_id]['vector_score'] = vector_score
            merged_results[doc_id]['vector_rank'] = i + 1
            merged_results[doc_id]['keyword_score'] = 0.0
            merged_results[doc_id]['keyword_rank'] = len(keyword_results) + 1
        
        # 处理关键词搜索结果
        for i, result in enumerate(keyword_results):
            doc_id = result['id']
            keyword_score = result.get('keyword_score', 0.0)
            
            if doc_id in merged_results:
                merged_results[doc_id]['keyword_score'] = keyword_score
                merged_results[doc_id]['keyword_rank'] = i + 1
            else:
                # 如果向量搜索中没有这个结果，添加它
                merged_results[doc_id] = result.copy()
                merged_results[doc_id]['vector_score'] = 0.0
                merged_results[doc_id]['vector_rank'] = len(vector_results) + 1
                merged_results[doc_id]['keyword_score'] = keyword_score
                merged_results[doc_id]['keyword_rank'] = i + 1
        
        # 计算混合分数
        for doc_id, result in merged_results.items():
            vector_score = result['vector_score']
            keyword_score = result['keyword_score']
            
            # 混合分数
            hybrid_score = (vector_score * vector_weight + 
                          keyword_score * keyword_weight)
            
            result['hybrid_score'] = hybrid_score
        
        # 按混合分数排序
        sorted_results = sorted(merged_results.values(), 
                              key=lambda x: x['hybrid_score'], 
                              reverse=True)
        
        return sorted_results
    
    def _sort_results(self, results: List[Dict[str, Any]], 
                     sort_by: str, sort_order: str) -> List[Dict[str, Any]]:
        """对结果进行排序"""
        try:
            reverse = (sort_order.lower() == "desc")
            
            def get_sort_key(result):
                payload = result.get('payload', {})
                value = payload.get(sort_by)
                
                # 处理不同类型的值
                if value is None:
                    return 0 if isinstance(value, (int, float)) else ""
                
                # 时间字段处理
                if sort_by in ['publish_time', 'crawl_time', 'stored_at']:
                    try:
                        if isinstance(value, str):
                            return datetime.fromisoformat(value.replace('Z', '+00:00'))
                        return value
                    except:
                        return datetime.min
                
                return value
            
            sorted_results = sorted(results, key=get_sort_key, reverse=reverse)
            return sorted_results
            
        except Exception as e:
            logger.error(f"结果排序失败: {str(e)}")
            return results
    
    def _post_process_results(self, results: List[Dict[str, Any]], 
                            query: str = "") -> List[Dict[str, Any]]:
        """后处理搜索结果"""
        processed_results = []
        
        for result in results:
            processed_result = result.copy()
            
            # 添加搜索元信息
            processed_result['search_metadata'] = {
                'search_time': datetime.now().isoformat(),
                'query': query,
                'similarity_score': result.get('score', 0.0)
            }
            
            # 提取和格式化关键字段
            payload = result.get('payload', {})
            
            # 生成摘要
            title = payload.get('title', '')
            content = payload.get('content', '')
            
            if content and len(content) > 200:
                # 简单的摘要生成
                summary = content[:200] + "..."
                processed_result['summary'] = summary
            
            # 高亮关键词（如果有查询）
            if query:
                highlighted_title = self._highlight_keywords(title, query)
                processed_result['highlighted_title'] = highlighted_title
            
            processed_results.append(processed_result)
        
        return processed_results
    
    def _highlight_keywords(self, text: str, query: str) -> str:
        """高亮关键词"""
        if not text or not query:
            return text
        
        # 提取查询关键词
        keywords = self._extract_keywords(query)
        
        highlighted_text = text
        
        for keyword in keywords:
            # 简单的高亮标记
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted_text = pattern.sub(f"**{keyword}**", highlighted_text)
        
        return highlighted_text
    
    def get_search_suggestions(self, partial_query: str, 
                             limit: int = 5) -> List[str]:
        """获取搜索建议"""
        # 这里可以实现基于历史搜索、热门关键词等的搜索建议
        # 简化实现：返回一些常见的金融搜索词
        
        financial_suggestions = [
            "股票分析", "市场行情", "财报分析", "投资策略", "风险评估",
            "行业研究", "公司公告", "政策解读", "经济数据", "技术分析"
        ]
        
        if not partial_query:
            return financial_suggestions[:limit]
        
        # 简单的模糊匹配
        suggestions = [s for s in financial_suggestions if partial_query.lower() in s.lower()]
        
        return suggestions[:limit]
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        return {
            'embedder_info': self.embedder.get_model_info(),
            'vector_store_info': self.vector_store.get_statistics(),
            'search_config': {
                'default_limit': self.default_limit,
                'max_limit': self.max_limit,
                'default_score_threshold': self.default_score_threshold
            }
        }
