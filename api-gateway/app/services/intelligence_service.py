"""
智能情报服务
实现投资情报的智能聚合、分析和监控功能
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import structlog
from collections import defaultdict, Counter
import hashlib
import json

from .search_service import search_service
from .elasticsearch_service import elasticsearch_service
from .qdrant_service import qdrant_service

logger = structlog.get_logger(__name__)


class IntelligenceService:
    """智能情报服务"""
    
    def __init__(self):
        self.search_service = search_service
        self.elasticsearch = elasticsearch_service
        self.qdrant = qdrant_service
        
        # 初始化NLP处理器
        self._nlp_processors = None
        self._embedder = None
        
    async def initialize(self):
        """初始化服务"""
        try:
            await self._initialize_nlp_processors()
            logger.info("智能情报服务初始化完成")
            return True
        except Exception as e:
            logger.error("智能情报服务初始化失败", error=str(e))
            return False
    
    async def _initialize_nlp_processors(self):
        """初始化NLP处理器"""
        try:
            import sys
            import os
            
            # 添加data-processor路径到Python路径
            data_processor_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data-processor')
            sys.path.append(data_processor_path)
            
            from nlp.sentiment_analysis import SentimentAnalyzer
            from nlp.text_classifier import TextClassifier
            from vector.embeddings import TextEmbedder
            
            self._nlp_processors = {
                'sentiment_analyzer': SentimentAnalyzer(model_type="dictionary"),
                'text_classifier': TextClassifier(classifier_type="rule_based"),
                'embedder': TextEmbedder(
                    model_type="sentence_transformers",
                    model_name="paraphrase-multilingual-MiniLM-L12-v2",
                    cache_embeddings=True
                )
            }
            
            logger.info("NLP处理器初始化完成")
            
        except Exception as e:
            logger.error("NLP处理器初始化失败", error=str(e))
            # 创建空的处理器字典，使用备用方案
            self._nlp_processors = {}
    
    async def generate_intelligence_report(self, topic: str, keywords: List[str], 
                                         time_range: int = 30, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        生成智能情报报告
        
        Args:
            topic: 分析主题
            keywords: 关键词列表
            time_range: 时间范围（天数）
            sources: 数据源筛选
            
        Returns:
            智能分析报告
        """
        logger.info("开始生成智能情报报告", topic=topic, keywords=keywords)
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=time_range)
            
            # 1. 搜索和聚合相关内容
            documents = await self._aggregate_content(topic, keywords, start_date, end_date, sources)
            
            if not documents:
                return self._create_empty_report(topic, time_range, start_date, end_date)
            
            # 2. 执行多维度分析
            analysis_results = await self._analyze_documents(documents)
            
            # 3. 生成趋势数据
            trend_data = await self._generate_trend_analysis(documents, start_date, end_date)
            
            # 4. 生成关键洞察
            insights = await self._extract_key_insights(documents, analysis_results, topic)
            
            # 5. 生成相关主题
            related_topics = await self._discover_related_topics(documents, keywords)
            
            # 6. 构建知识图谱
            knowledge_graph = await self._build_knowledge_graph(topic, keywords, related_topics, documents)
            
            # 7. 生成摘要
            summary = self._generate_summary(topic, time_range, len(documents), analysis_results)
            
            # 8. 构建报告
            report = {
                'topic': topic,
                'keywords': keywords,
                'summary': summary,
                'sentiment': analysis_results.get('sentiment_stats', {}),
                'trend_data': trend_data,
                'key_insights': insights,
                'related_topics': related_topics,
                'knowledge_graph': knowledge_graph,
                'classification': analysis_results.get('classification_stats', {}),
                'data_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': time_range,
                    'total_documents': len(documents)
                },
                'generated_at': datetime.now().isoformat()
            }
            
            logger.info("智能情报报告生成完成", 
                       topic=topic, 
                       documents_count=len(documents),
                       insights_count=len(insights),
                       knowledge_graph_nodes=len(knowledge_graph.get('nodes', [])))
            
            return report
            
        except Exception as e:
            logger.error("智能情报报告生成失败", topic=topic, error=str(e))
            return self._create_error_report(topic, str(e))
    
    async def _aggregate_content(self, topic: str, keywords: List[str], 
                               start_date: datetime, end_date: datetime,
                               sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """智能内容聚合"""
        try:
            # 1. 基于关键词的搜索
            keyword_documents = await self._search_by_keywords(topic, keywords, start_date, end_date, sources)
            
            # 2. 基于语义的搜索
            semantic_documents = await self._search_by_semantics(topic, keywords, start_date, end_date, sources)
            
            # 3. 内容去重和聚合
            aggregated_documents = await self._deduplicate_and_merge(keyword_documents, semantic_documents)
            
            # 4. 内容质量过滤
            filtered_documents = await self._filter_by_quality(aggregated_documents)
            
            # 5. 相关性排序
            ranked_documents = await self._rank_by_relevance(filtered_documents, topic, keywords)
            
            logger.info(f"内容聚合完成: 关键词搜索{len(keyword_documents)}条, "
                       f"语义搜索{len(semantic_documents)}条, "
                       f"聚合后{len(aggregated_documents)}条, "
                       f"过滤后{len(filtered_documents)}条, "
                       f"最终{len(ranked_documents)}条")
            
            return ranked_documents
            
        except Exception as e:
            logger.error("内容聚合失败", error=str(e))
            return []
    
    async def _search_by_keywords(self, topic: str, keywords: List[str],
                                start_date: datetime, end_date: datetime,
                                sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """基于关键词搜索"""
        try:
            query_terms = [topic] + keywords
            query = " OR ".join(query_terms)
            
            filters = {
                "time_range": {
                    "gte": start_date.isoformat(),
                    "lte": end_date.isoformat()
                }
            }
            
            if sources:
                filters["sources"] = sources
            
            search_result = await self.search_service.search(
                query=query,
                search_type="keyword",
                filters=filters,
                page=1,
                page_size=100,
                sort_by="relevance"
            )
            
            return search_result.get("results", [])
            
        except Exception as e:
            logger.error("关键词搜索失败", error=str(e))
            return []
    
    async def _search_by_semantics(self, topic: str, keywords: List[str],
                                 start_date: datetime, end_date: datetime,
                                 sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """基于语义搜索"""
        try:
            # 构建语义查询
            semantic_query = f"{topic} {' '.join(keywords)}"
            
            filters = {
                "time_range": {
                    "gte": start_date.isoformat(),
                    "lte": end_date.isoformat()
                }
            }
            
            if sources:
                filters["sources"] = sources
            
            search_result = await self.search_service.search(
                query=semantic_query,
                search_type="semantic",
                filters=filters,
                page=1,
                page_size=100
            )
            
            return search_result.get("results", [])
            
        except Exception as e:
            logger.error("语义搜索失败", error=str(e))
            return []
    
    async def _deduplicate_and_merge(self, *document_lists) -> List[Dict[str, Any]]:
        """去重和合并文档"""
        try:
            seen_ids = set()
            seen_hashes = set()
            merged_documents = []
            
            for doc_list in document_lists:
                for doc in doc_list:
                    # 基于ID去重
                    doc_id = doc.get('id')
                    if doc_id and doc_id in seen_ids:
                        continue
                    
                    # 基于内容哈希去重
                    content = doc.get('content', '') + doc.get('title', '')
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    if content_hash in seen_hashes:
                        continue
                    
                    if doc_id:
                        seen_ids.add(doc_id)
                    seen_hashes.add(content_hash)
                    merged_documents.append(doc)
            
            logger.info(f"文档去重完成: {len(merged_documents)}条唯一文档")
            return merged_documents
            
        except Exception as e:
            logger.error("文档去重失败", error=str(e))
            # 返回第一个列表作为备用
            return document_lists[0] if document_lists else []
    
    async def _filter_by_quality(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于质量过滤文档"""
        try:
            filtered_docs = []
            
            for doc in documents:
                # 基本质量检查
                title = doc.get('title', '')
                content = doc.get('content', '')
                
                # 过滤条件
                if len(title) < 10 and len(content) < 50:
                    continue  # 内容太短
                
                if not title.strip() and not content.strip():
                    continue  # 空文档
                
                # 检查是否为垃圾内容
                if self._is_spam_content(title, content):
                    continue
                
                filtered_docs.append(doc)
            
            logger.info(f"质量过滤完成: 保留{len(filtered_docs)}/{len(documents)}条文档")
            return filtered_docs
            
        except Exception as e:
            logger.error("质量过滤失败", error=str(e))
            return documents
    
    def _is_spam_content(self, title: str, content: str) -> bool:
        """检查是否为垃圾内容"""
        spam_indicators = [
            '测试', '广告', '推广', '联系方式', '电话', '微信',
            '免费', '优惠', '特价', '限时', '秒杀'
        ]
        
        text = (title + ' ' + content).lower()
        spam_count = sum(1 for indicator in spam_indicators if indicator in text)
        
        return spam_count >= 3  # 如果包含3个或以上垃圾指示词，认为是垃圾内容
    
    async def _rank_by_relevance(self, documents: List[Dict[str, Any]], 
                                topic: str, keywords: List[str]) -> List[Dict[str, Any]]:
        """基于相关性排序"""
        try:
            # 计算每个文档的相关性得分
            for doc in documents:
                relevance_score = self._calculate_relevance_score(doc, topic, keywords)
                doc['final_relevance_score'] = relevance_score
            
            # 按相关性得分排序
            sorted_docs = sorted(documents, key=lambda x: x.get('final_relevance_score', 0), reverse=True)
            
            # 限制返回数量
            return sorted_docs[:200]  # 最多返回200条最相关的文档
            
        except Exception as e:
            logger.error("相关性排序失败", error=str(e))
            return documents
    
    def _calculate_relevance_score(self, doc: Dict[str, Any], topic: str, keywords: List[str]) -> float:
        """计算相关性得分"""
        try:
            title = doc.get('title', '').lower()
            content = doc.get('content', '').lower()
            text = title + ' ' + content
            
            score = 0.0
            
            # 主题匹配（权重最高）
            if topic.lower() in text:
                score += 3.0
            
            # 关键词匹配
            for keyword in keywords:
                keyword_count = text.count(keyword.lower())
                score += keyword_count * 1.5
            
            # 标题匹配加权
            title_matches = sum(1 for keyword in keywords if keyword.lower() in title)
            score += title_matches * 2.0
            
            # 基于原始相关性得分
            original_score = doc.get('relevance_score', 0)
            score += original_score * 0.5
            
            # 时间新鲜度加权
            pub_time_str = doc.get('publish_time') or doc.get('created_at')
            if pub_time_str:
                try:
                    if isinstance(pub_time_str, str):
                        pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                    else:
                        pub_time = pub_time_str
                    
                    # 越新的内容分数越高
                    days_old = (datetime.now(pub_time.tzinfo) - pub_time).days
                    freshness_score = max(0, 1.0 - days_old / 30)  # 30天内的内容有额外加分
                    score += freshness_score * 0.5
                    
                except Exception:
                    pass
            
            return score
            
        except Exception as e:
            logger.error("计算相关性得分失败", error=str(e))
            return 0.0
    
    async def _analyze_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析文档"""
        try:
            analysis_results = {}
            
            # 提取文本
            texts = [doc.get("content", "") + " " + doc.get("title", "") for doc in documents]
            titles = [doc.get("title", "") for doc in documents]
            
            if not texts:
                return analysis_results
            
            # 限制分析数量以提高性能
            max_analyze = 100
            texts = texts[:max_analyze]
            titles = titles[:max_analyze]
            
            # 情感分析
            if self._nlp_processors and 'sentiment_analyzer' in self._nlp_processors:
                try:
                    sentiment_analyzer = self._nlp_processors['sentiment_analyzer']
                    sentiment_results = sentiment_analyzer.batch_analyze(texts)
                    analysis_results['sentiment_stats'] = sentiment_analyzer.get_sentiment_statistics(sentiment_results)
                except Exception as e:
                    logger.error("情感分析失败", error=str(e))
            
            # 文本分类
            if self._nlp_processors and 'text_classifier' in self._nlp_processors:
                try:
                    text_classifier = self._nlp_processors['text_classifier']
                    classification_results = text_classifier.classify_batch(texts, titles)
                    analysis_results['classification_stats'] = text_classifier.get_classification_statistics(classification_results)
                except Exception as e:
                    logger.error("文本分类失败", error=str(e))
            
            logger.info("文档分析完成", analyzed_count=len(texts))
            return analysis_results
            
        except Exception as e:
            logger.error("文档分析失败", error=str(e))
            return {}
    
    async def _generate_trend_analysis(self, documents: List[Dict[str, Any]], 
                                     start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """生成趋势分析和异常检测"""
        try:
            # 按日期分组文档
            daily_counts = defaultdict(int)
            daily_sentiment = defaultdict(list)
            daily_importance = defaultdict(list)
            
            for doc in documents:
                # 解析文档发布时间
                pub_time_str = doc.get("publish_time") or doc.get("created_at")
                if not pub_time_str:
                    continue
                    
                try:
                    if isinstance(pub_time_str, str):
                        pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00'))
                    else:
                        pub_time = pub_time_str
                        
                    date_key = pub_time.date()
                    daily_counts[date_key] += 1
                    
                    # 情感评分
                    title = doc.get("title", "")
                    content = doc.get("content", "")
                    text = title + " " + content
                    
                    sentiment_score = self._calculate_simple_sentiment(text)
                    daily_sentiment[date_key].append(sentiment_score)
                    
                    # 重要性评分
                    importance_score = self._calculate_importance_score(text, title)
                    daily_importance[date_key].append(importance_score)
                    
                except Exception:
                    continue
            
            # 生成基础趋势数据
            trend_data = []
            volumes = []
            sentiments = []
            importance_values = []
            
            current_date = start_date.date()
            end_date_only = end_date.date()
            
            while current_date <= end_date_only:
                volume = daily_counts.get(current_date, 0)
                day_sentiments = daily_sentiment.get(current_date, [0])
                day_importance = daily_importance.get(current_date, [0])
                
                avg_sentiment = sum(day_sentiments) / len(day_sentiments) if day_sentiments else 0
                avg_importance = sum(day_importance) / len(day_importance) if day_importance else 0
                
                # 将情感分数转换为趋势值（50为基准）
                trend_value = 50 + avg_sentiment * 30 + min(volume / 5, 20) + avg_importance * 10
                
                trend_point = {
                    'date': current_date.isoformat(),
                    'value': round(trend_value, 2),
                    'volume': volume,
                    'sentiment': round(avg_sentiment, 3),
                    'importance': round(avg_importance, 3),
                    'anomaly': False,
                    'anomaly_score': 0.0,
                    'anomaly_reason': ''
                }
                
                trend_data.append(trend_point)
                
                # 收集数据用于异常检测
                volumes.append(volume)
                sentiments.append(avg_sentiment)
                importance_values.append(avg_importance)
                
                current_date += timedelta(days=1)
            
            # 执行异常检测
            self._detect_anomalies(trend_data, volumes, sentiments, importance_values)
            
            logger.info(f"趋势分析完成: {len(trend_data)}个数据点")
            return trend_data
            
        except Exception as e:
            logger.error("趋势分析失败", error=str(e))
            return []
    
    def _calculate_importance_score(self, text: str, title: str) -> float:
        """计算重要性得分"""
        try:
            # 重要性关键词
            high_importance_words = {
                '重大', '重要', '紧急', '突发', '首次', '历史', '创新高', '创新低',
                '涨停', '跌停', '停牌', '复牌', '退市', 'IPO', '并购', '重组',
                '监管', '政策', '央行', '证监会', '处罚', '违规', '调查'
            }
            
            medium_importance_words = {
                '公告', '披露', '变动', '调整', '增长', '下降', '合作', '签约',
                '业绩', '财报', '分红', '投资', '评级'
            }
            
            # 计算重要性得分
            text_lower = text.lower()
            title_lower = title.lower()
            
            score = 0.0
            
            # 高重要性词汇（标题权重更高）
            for word in high_importance_words:
                if word in title_lower:
                    score += 3.0
                elif word in text_lower:
                    score += 1.5
            
            # 中等重要性词汇
            for word in medium_importance_words:
                if word in title_lower:
                    score += 2.0
                elif word in text_lower:
                    score += 1.0
            
            # 根据文档长度调整
            if len(text) > 1000:
                score *= 1.2
            elif len(text) < 200:
                score *= 0.8
            
            # 标准化到0-1范围
            return min(1.0, score / 10.0)
            
        except Exception as e:
            logger.error("计算重要性得分失败", error=str(e))
            return 0.0
    
    def _detect_anomalies(self, trend_data: List[Dict[str, Any]], 
                         volumes: List[int], sentiments: List[float], 
                         importance_values: List[float]):
        """检测异常"""
        try:
            if len(trend_data) < 3:
                return  # 数据太少无法检测异常
            
            # 计算统计指标
            import statistics
            
            # 音量异常检测
            if len(volumes) > 1:
                volume_mean = statistics.mean(volumes)
                volume_stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0
                volume_threshold = volume_mean + 2 * volume_stdev
                
                for i, trend_point in enumerate(trend_data):
                    volume = volumes[i]
                    if volume > volume_threshold and volume > volume_mean * 2:
                        trend_point['anomaly'] = True
                        trend_point['anomaly_score'] = min(1.0, (volume - volume_mean) / max(volume_mean, 1))
                        trend_point['anomaly_reason'] = f'信息量异常增加：{volume}条（平均{volume_mean:.1f}条）'
            
            # 情感异常检测
            if len(sentiments) > 1:
                sentiment_mean = statistics.mean(sentiments)
                sentiment_stdev = statistics.stdev(sentiments) if len(sentiments) > 1 else 0
                
                for i, trend_point in enumerate(trend_data):
                    sentiment = sentiments[i]
                    if abs(sentiment - sentiment_mean) > 2 * sentiment_stdev and abs(sentiment) > 0.5:
                        if not trend_point['anomaly']:
                            trend_point['anomaly'] = True
                            trend_point['anomaly_score'] = min(1.0, abs(sentiment - sentiment_mean) / max(sentiment_stdev, 0.1))
                        
                        sentiment_desc = "极度乐观" if sentiment > 0.5 else "极度悲观"
                        if trend_point['anomaly_reason']:
                            trend_point['anomaly_reason'] += f"；情感{sentiment_desc}（{sentiment:.2f}）"
                        else:
                            trend_point['anomaly_reason'] = f"情感{sentiment_desc}（{sentiment:.2f}）"
            
            # 重要性异常检测
            if len(importance_values) > 1:
                importance_mean = statistics.mean(importance_values)
                importance_threshold = importance_mean + statistics.stdev(importance_values) if len(importance_values) > 1 else importance_mean
                
                for i, trend_point in enumerate(trend_data):
                    importance = importance_values[i]
                    if importance > importance_threshold and importance > 0.7:
                        if not trend_point['anomaly']:
                            trend_point['anomaly'] = True
                            trend_point['anomaly_score'] = importance
                        
                        if trend_point['anomaly_reason']:
                            trend_point['anomaly_reason'] += f"；重要事件密集（{importance:.2f}）"
                        else:
                            trend_point['anomaly_reason'] = f"重要事件密集（{importance:.2f}）"
            
            # 连续异常检测
            self._detect_consecutive_anomalies(trend_data)
            
            anomaly_count = sum(1 for point in trend_data if point['anomaly'])
            logger.info(f"异常检测完成: 发现{anomaly_count}个异常点")
            
        except Exception as e:
            logger.error("异常检测失败", error=str(e))
    
    def _detect_consecutive_anomalies(self, trend_data: List[Dict[str, Any]]):
        """检测连续异常模式"""
        try:
            # 检测连续的高活跃度
            consecutive_high = 0
            for i, trend_point in enumerate(trend_data):
                if trend_point['volume'] > 0 or trend_point['importance'] > 0.5:
                    consecutive_high += 1
                else:
                    if consecutive_high >= 3:
                        # 标记连续高活跃期
                        for j in range(max(0, i - consecutive_high), i):
                            if not trend_data[j]['anomaly']:
                                trend_data[j]['anomaly'] = True
                                trend_data[j]['anomaly_score'] = 0.6
                                trend_data[j]['anomaly_reason'] = f'连续高活跃期（{consecutive_high}天）'
                    consecutive_high = 0
            
            # 检查最后一段连续高活跃
            if consecutive_high >= 3:
                for j in range(max(0, len(trend_data) - consecutive_high), len(trend_data)):
                    if not trend_data[j]['anomaly']:
                        trend_data[j]['anomaly'] = True
                        trend_data[j]['anomaly_score'] = 0.6
                        trend_data[j]['anomaly_reason'] = f'连续高活跃期（{consecutive_high}天）'
            
        except Exception as e:
            logger.error("连续异常检测失败", error=str(e))
    
    def _calculate_simple_sentiment(self, text: str) -> float:
        """计算简单情感分数"""
        positive_words = {'涨', '增长', '上升', '利好', '好', '优', '强', '高', '升', '涨停', '买入', '推荐'}
        negative_words = {'跌', '下降', '下跌', '利空', '差', '弱', '低', '跌停', '亏损', '风险', '卖出', '减持'}
        
        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)
        
        if pos_count + neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count)
    
    async def _extract_key_insights(self, documents: List[Dict[str, Any]], 
                                   analysis_results: Dict[str, Any], topic: str) -> List[Dict[str, Any]]:
        """提取关键洞察"""
        try:
            insights = []
            
            # 1. 文档数量洞察
            doc_count = len(documents)
            if doc_count > 50:
                insights.append({
                    'title': '高关注度主题',
                    'description': f'{topic}获得了较高的市场关注度，共发现{doc_count}条相关信息',
                    'confidence': 0.9,
                    'type': 'volume',
                    'supporting_docs': [doc.get('id', f'doc_{i}') for i, doc in enumerate(documents[:10])]
                })
            elif doc_count < 10:
                insights.append({
                    'title': '信息较少主题',
                    'description': f'{topic}相关信息较少（{doc_count}条），可能是新兴或小众领域',
                    'confidence': 0.7,
                    'type': 'volume',
                    'supporting_docs': [doc.get('id', f'doc_{i}') for i, doc in enumerate(documents)]
                })
            
            # 2. 情感洞察
            sentiment_stats = analysis_results.get('sentiment_stats', {})
            if sentiment_stats:
                avg_score = sentiment_stats.get('avg_score', 0)
                label_dist = sentiment_stats.get('label_distribution', {})
                
                pos_ratio = label_dist.get('positive', {}).get('percentage', 0) / 100
                neg_ratio = label_dist.get('negative', {}).get('percentage', 0) / 100
                
                if pos_ratio > 0.6:
                    insights.append({
                        'title': '市场情绪积极',
                        'description': f'针对{topic}的市场情绪整体积极，正面信息占比{pos_ratio:.1%}',
                        'confidence': 0.8,
                        'type': 'sentiment',
                        'supporting_docs': []
                    })
                elif neg_ratio > 0.6:
                    insights.append({
                        'title': '市场情绪偏谨慎',
                        'description': f'针对{topic}的市场情绪偏谨慎，负面信息占比{neg_ratio:.1%}',
                        'confidence': 0.8,
                        'type': 'sentiment',
                        'supporting_docs': []
                    })
            
            # 3. 分类洞察
            classification_stats = analysis_results.get('classification_stats', {})
            if classification_stats:
                news_dist = classification_stats.get('news_type_distribution', {})
                if news_dist:
                    # 找出占主导地位的新闻类型
                    main_type = max(news_dist.items(), key=lambda x: x[1].get('count', 0))
                    if main_type:
                        type_name, type_info = main_type
                        ratio = type_info.get('percentage', 0) / 100
                        if ratio > 0.4:
                            insights.append({
                                'title': f'{type_name}信息集中',
                                'description': f'{topic}相关信息中{type_name}类占主导地位（{ratio:.1%}），需要关注该领域动态',
                                'confidence': 0.7,
                                'type': 'classification',
                                'supporting_docs': []
                            })
            
            logger.info(f"提取了{len(insights)}个关键洞察")
            return insights
            
        except Exception as e:
            logger.error("提取关键洞察失败", error=str(e))
            return []
    
    async def _discover_related_topics(self, documents: List[Dict[str, Any]], 
                                     keywords: List[str]) -> List[str]:
        """发现相关主题"""
        try:
            # 提取所有文本内容
            all_text = " ".join([
                doc.get("title", "") + " " + doc.get("content", "") 
                for doc in documents
            ])
            
            # 简单的关键词提取
            import re
            words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text)  # 提取中文词
            
            # 过滤掉原有关键词和常见词
            stop_words = set(keywords + ['公司', '市场', '投资', '股票', '证券', '金融', '经济', '发展'])
            filtered_words = [word for word in words if word not in stop_words and len(word) >= 2]
            
            # 统计词频
            word_counter = Counter(filtered_words)
            related_topics = [word for word, count in word_counter.most_common(20) if count >= 3]
            
            logger.info(f"发现了{len(related_topics)}个相关主题")
            return related_topics[:10]  # 返回前10个相关主题
            
        except Exception as e:
            logger.error("发现相关主题失败", error=str(e))
            return []
    
    async def _build_knowledge_graph(self, topic: str, keywords: List[str], 
                                   related_topics: List[str], documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建投资主题知识图谱"""
        try:
            logger.info("开始构建知识图谱", topic=topic)
            
            # 1. 构建节点
            nodes = []
            node_id = 0
            
            # 主题节点（中心节点）
            main_node = {
                'id': str(node_id),
                'label': topic,
                'type': 'main_topic',
                'size': 30,
                'color': '#ff6b6b',
                'importance': 1.0,
                'document_count': len(documents)
            }
            nodes.append(main_node)
            node_id += 1
            
            # 关键词节点
            keyword_nodes = {}
            for keyword in keywords:
                if keyword != topic:  # 避免重复
                    node = {
                        'id': str(node_id),
                        'label': keyword,
                        'type': 'keyword',
                        'size': 20,
                        'color': '#4ecdc4',
                        'importance': 0.8,
                        'document_count': self._count_documents_containing(documents, keyword)
                    }
                    nodes.append(node)
                    keyword_nodes[keyword] = node['id']
                    node_id += 1
            
            # 相关主题节点
            related_nodes = {}
            for i, related_topic in enumerate(related_topics[:10]):  # 限制数量
                if related_topic not in keywords and related_topic != topic:
                    doc_count = self._count_documents_containing(documents, related_topic)
                    if doc_count >= 2:  # 只包含有足够文档支撑的主题
                        importance = min(0.7, doc_count / len(documents) * 2)
                        node = {
                            'id': str(node_id),
                            'label': related_topic,
                            'type': 'related_topic',
                            'size': 15 + importance * 10,
                            'color': '#45b7d1',
                            'importance': importance,
                            'document_count': doc_count
                        }
                        nodes.append(node)
                        related_nodes[related_topic] = node['id']
                        node_id += 1
            
            # 2. 构建边关系
            edges = []
            edge_id = 0
            
            # 主题与关键词的连接
            for keyword, keyword_node_id in keyword_nodes.items():
                co_occurrence = self._calculate_co_occurrence(documents, topic, keyword)
                if co_occurrence > 0.1:
                    edge = {
                        'id': str(edge_id),
                        'source': main_node['id'],
                        'target': keyword_node_id,
                        'weight': co_occurrence,
                        'type': 'keyword_relation',
                        'color': '#95a5a6',
                        'width': 2 + co_occurrence * 3
                    }
                    edges.append(edge)
                    edge_id += 1
            
            # 主题与相关主题的连接
            for related_topic, related_node_id in related_nodes.items():
                co_occurrence = self._calculate_co_occurrence(documents, topic, related_topic)
                if co_occurrence > 0.05:
                    edge = {
                        'id': str(edge_id),
                        'source': main_node['id'],
                        'target': related_node_id,
                        'weight': co_occurrence,
                        'type': 'topic_relation',
                        'color': '#bdc3c7',
                        'width': 1 + co_occurrence * 4
                    }
                    edges.append(edge)
                    edge_id += 1
            
            # 关键词之间的连接
            keyword_list = list(keyword_nodes.keys())
            for i, keyword1 in enumerate(keyword_list):
                for keyword2 in keyword_list[i+1:]:
                    co_occurrence = self._calculate_co_occurrence(documents, keyword1, keyword2)
                    if co_occurrence > 0.2:  # 较高的阈值，只显示强关联
                        edge = {
                            'id': str(edge_id),
                            'source': keyword_nodes[keyword1],
                            'target': keyword_nodes[keyword2],
                            'weight': co_occurrence,
                            'type': 'keyword_keyword_relation',
                            'color': '#ecf0f1',
                            'width': 1 + co_occurrence * 2
                        }
                        edges.append(edge)
                        edge_id += 1
            
            # 3. 识别核心概念聚类
            clusters = self._identify_concept_clusters(nodes, edges)
            
            # 4. 构建知识图谱
            knowledge_graph = {
                'nodes': nodes,
                'edges': edges,
                'clusters': clusters,
                'statistics': {
                    'total_nodes': len(nodes),
                    'total_edges': len(edges),
                    'main_topic': topic,
                    'keywords_count': len(keyword_nodes),
                    'related_topics_count': len(related_nodes),
                    'document_base': len(documents)
                },
                'layout_settings': {
                    'algorithm': 'force_directed',
                    'iterations': 100,
                    'repulsion_strength': 1000,
                    'attraction_strength': 0.1
                }
            }
            
            logger.info(f"知识图谱构建完成: {len(nodes)}个节点, {len(edges)}条边")
            return knowledge_graph
            
        except Exception as e:
            logger.error("知识图谱构建失败", error=str(e))
            return {'nodes': [], 'edges': [], 'clusters': []}
    
    def _count_documents_containing(self, documents: List[Dict[str, Any]], term: str) -> int:
        """计算包含指定词汇的文档数量"""
        count = 0
        term_lower = term.lower()
        
        for doc in documents:
            title = doc.get('title', '').lower()
            content = doc.get('content', '').lower()
            if term_lower in title or term_lower in content:
                count += 1
                
        return count
    
    def _calculate_co_occurrence(self, documents: List[Dict[str, Any]], term1: str, term2: str) -> float:
        """计算两个词汇的共现频率"""
        try:
            term1_lower = term1.lower()
            term2_lower = term2.lower()
            
            term1_docs = 0
            term2_docs = 0
            both_docs = 0
            
            for doc in documents:
                title = doc.get('title', '').lower()
                content = doc.get('content', '').lower()
                text = title + ' ' + content
                
                has_term1 = term1_lower in text
                has_term2 = term2_lower in text
                
                if has_term1:
                    term1_docs += 1
                if has_term2:
                    term2_docs += 1
                if has_term1 and has_term2:
                    both_docs += 1
            
            # 计算Jaccard系数
            if term1_docs + term2_docs - both_docs == 0:
                return 0.0
                
            jaccard = both_docs / (term1_docs + term2_docs - both_docs)
            return jaccard
            
        except Exception as e:
            logger.error("计算共现频率失败", error=str(e))
            return 0.0
    
    def _identify_concept_clusters(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别概念聚类"""
        try:
            clusters = []
            
            # 基于节点类型的基础聚类
            keyword_nodes = [node for node in nodes if node['type'] == 'keyword']
            related_topic_nodes = [node for node in nodes if node['type'] == 'related_topic']
            
            if keyword_nodes:
                clusters.append({
                    'id': 'keywords_cluster',
                    'name': '核心关键词',
                    'type': 'keywords',
                    'nodes': [node['id'] for node in keyword_nodes],
                    'color': '#4ecdc4',
                    'description': '与主题直接相关的核心关键词'
                })
            
            if related_topic_nodes:
                # 根据重要性分组相关主题
                high_importance = [node for node in related_topic_nodes if node['importance'] > 0.5]
                medium_importance = [node for node in related_topic_nodes if 0.2 <= node['importance'] <= 0.5]
                
                if high_importance:
                    clusters.append({
                        'id': 'high_relevance_cluster',
                        'name': '高相关性主题',
                        'type': 'high_relevance',
                        'nodes': [node['id'] for node in high_importance],
                        'color': '#45b7d1',
                        'description': '与主题高度相关的扩展主题'
                    })
                
                if medium_importance:
                    clusters.append({
                        'id': 'medium_relevance_cluster',
                        'name': '中等相关性主题',
                        'type': 'medium_relevance',
                        'nodes': [node['id'] for node in medium_importance],
                        'color': '#a8dadc',
                        'description': '与主题中等相关的周边主题'
                    })
            
            return clusters
            
        except Exception as e:
            logger.error("概念聚类识别失败", error=str(e))
            return []
    
    def _generate_summary(self, topic: str, time_range: int, doc_count: int, 
                         analysis_results: Dict[str, Any]) -> str:
        """生成摘要"""
        try:
            # 基础信息
            summary = f"基于{time_range}天的数据分析，{topic}主题共收集到{doc_count}条相关信息。"
            
            # 情感分析摘要
            sentiment_stats = analysis_results.get('sentiment_stats', {})
            if sentiment_stats:
                avg_sentiment = sentiment_stats.get('avg_score', 0.0)
                if avg_sentiment > 0.2:
                    summary += "整体市场情感偏正面，"
                elif avg_sentiment < -0.2:
                    summary += "整体市场情感偏负面，"
                else:
                    summary += "整体市场情感中性，"
            
            # 分类统计摘要
            classification_stats = analysis_results.get('classification_stats', {})
            if classification_stats:
                news_dist = classification_stats.get('news_type_distribution', {})
                if news_dist:
                    main_type = max(news_dist.items(), key=lambda x: x[1].get('count', 0))[0]
                    summary += f"以{main_type}类信息为主。"
                else:
                    summary += "信息类型多样。"
            else:
                summary += "信息类型多样。"
            
            # 投资建议
            if sentiment_stats:
                avg_sentiment = sentiment_stats.get('avg_score', 0.0)
                if avg_sentiment > 0.3:
                    summary += "市场对该主题持积极态度，建议持续关注相关发展动态。"
                elif avg_sentiment < -0.3:
                    summary += "市场对该主题存在担忧，需要谨慎关注风险因素。"
                else:
                    summary += "市场对该主题态度相对理性，建议综合多方面因素进行判断。"
            
            return summary
            
        except Exception as e:
            logger.error("生成摘要失败", error=str(e))
            return f"针对{topic}的分析报告生成遇到问题，请稍后重试。"
    
    def _create_empty_report(self, topic: str, time_range: int, 
                           start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """创建空报告"""
        return {
            'topic': topic,
            'summary': f"在指定的{time_range}天时间范围内，未找到与"{topic}"相关的足够信息。建议扩大时间范围或调整搜索关键词。",
            'sentiment': {
                'avg_score': 0.0,
                'label_distribution': {
                    'positive': {'count': 0, 'percentage': 33.3},
                    'negative': {'count': 0, 'percentage': 33.3},
                    'neutral': {'count': 0, 'percentage': 33.4}
                }
            },
            'trend_data': [],
            'key_insights': [{
                'title': '数据不足',
                'description': f'当前时间范围内关于{topic}的信息较少，建议扩大搜索范围',
                'confidence': 0.9,
                'type': 'system',
                'supporting_docs': []
            }],
            'related_topics': [],
            'classification': {},
            'data_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': time_range,
                'total_documents': 0
            },
            'generated_at': datetime.now().isoformat()
        }
    
    def _create_error_report(self, topic: str, error: str) -> Dict[str, Any]:
        """创建错误报告"""
        return {
            'topic': topic,
            'error': error,
            'summary': f'生成{topic}的分析报告时遇到错误：{error}',
            'generated_at': datetime.now().isoformat()
        }


# 全局智能情报服务实例
intelligence_service = IntelligenceService()
