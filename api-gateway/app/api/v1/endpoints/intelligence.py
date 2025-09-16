"""
智能分析API端点
实现投资情报的智能分析功能
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


# Pydantic模型定义
class AnalysisRequest(BaseModel):
    """分析请求模型"""
    topic: str = Field(..., description="分析主题", min_length=1, max_length=100)
    keywords: List[str] = Field(..., description="关键词列表", min_items=1)
    time_range: Optional[int] = Field(default=30, description="时间范围(天)", ge=1, le=365)
    sources: Optional[List[str]] = Field(default=None, description="数据源筛选")


class SentimentData(BaseModel):
    """情感分析数据"""
    positive: float = Field(..., description="正面情绪比例", ge=0, le=1)
    neutral: float = Field(..., description="中性情绪比例", ge=0, le=1)
    negative: float = Field(..., description="负面情绪比例", ge=0, le=1)
    score: float = Field(..., description="整体情感得分", ge=-1, le=1)


class TrendPoint(BaseModel):
    """趋势数据点"""
    date: datetime = Field(..., description="日期")
    value: float = Field(..., description="数值")
    volume: int = Field(default=0, description="文档数量")


class KeyInsight(BaseModel):
    """关键洞察"""
    title: str = Field(..., description="洞察标题")
    description: str = Field(..., description="洞察描述")
    confidence: float = Field(..., description="置信度", ge=0, le=1)
    supporting_docs: List[str] = Field(..., description="支撑文档ID列表")


class IntelligenceReport(BaseModel):
    """智能分析报告"""
    topic: str = Field(..., description="分析主题")
    summary: str = Field(..., description="分析摘要")
    sentiment: SentimentData = Field(..., description="情感分析")
    trend_data: List[TrendPoint] = Field(..., description="趋势数据")
    key_insights: List[KeyInsight] = Field(..., description="关键洞察")
    related_topics: List[str] = Field(..., description="相关主题")
    generated_at: datetime = Field(..., description="生成时间")
    data_period: dict = Field(..., description="数据时间段")


class MonitoringTask(BaseModel):
    """监控任务模型"""
    id: str = Field(..., description="任务ID")
    topic: str = Field(..., description="监控主题")
    keywords: List[str] = Field(..., description="关键词")
    status: str = Field(..., description="状态: active, paused, completed")
    created_at: datetime = Field(..., description="创建时间")
    last_updated: datetime = Field(..., description="最后更新时间")
    alert_threshold: float = Field(default=0.8, description="预警阈值")


@router.post("/analyze", response_model=IntelligenceReport)
async def create_intelligence_analysis(request: AnalysisRequest):
    """
    创建智能分析报告
    基于指定主题和关键词生成深度分析报告
    """
    logger.info(
        "开始智能分析",
        topic=request.topic,
        keywords=request.keywords,
        time_range=request.time_range
    )
    
    try:
        # TODO: 实现真实的智能分析逻辑
        # 1. 从Elasticsearch搜索相关文档
        # 2. 使用NLP模型进行情感分析
        # 3. 计算趋势数据
        # 4. 提取关键洞察
        # 5. 生成分析报告
        
        report = await _generate_intelligence_report(request)
        
        logger.info(
            "智能分析完成",
            topic=request.topic,
            insights_count=len(report.key_insights)
        )
        
        return report
        
    except Exception as e:
        logger.error("智能分析失败", topic=request.topic, error=str(e))
        raise HTTPException(status_code=500, detail=f"智能分析失败: {str(e)}")


@router.get("/reports")
async def list_intelligence_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    topic: Optional[str] = Query(None, description="主题筛选")
):
    """
    获取智能分析报告列表
    """
    logger.info("获取分析报告列表", page=page, page_size=page_size)
    
    try:
        # TODO: 从数据库获取报告列表
        reports = await _get_intelligence_reports(page, page_size, topic)
        
        return {
            "reports": reports,
            "total_count": 50,  # 模拟总数
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        logger.error("获取报告列表失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"获取报告列表失败: {str(e)}")


@router.post("/monitoring", response_model=MonitoringTask)
async def create_monitoring_task(request: AnalysisRequest):
    """
    创建主题监控任务
    持续监控指定主题的投资情报变化
    """
    logger.info("创建监控任务", topic=request.topic)
    
    try:
        # TODO: 实现监控任务创建逻辑
        # 1. 创建数据库记录
        # 2. 配置Celery定时任务
        # 3. 初始化监控指标
        
        task = MonitoringTask(
            id=f"monitor_{int(datetime.now().timestamp())}",
            topic=request.topic,
            keywords=request.keywords,
            status="active",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        
        await _save_monitoring_task(task)
        await _schedule_monitoring_job(task)
        
        logger.info("监控任务创建成功", task_id=task.id)
        return task
        
    except Exception as e:
        logger.error("创建监控任务失败", topic=request.topic, error=str(e))
        raise HTTPException(status_code=500, detail=f"创建监控任务失败: {str(e)}")


@router.get("/monitoring")
async def list_monitoring_tasks():
    """
    获取监控任务列表
    """
    logger.info("获取监控任务列表")
    
    try:
        tasks = await _get_monitoring_tasks()
        
        return {
            "tasks": tasks,
            "total_count": len(tasks)
        }
        
    except Exception as e:
        logger.error("获取监控任务失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"获取监控任务失败: {str(e)}")


@router.get("/trends/{topic}")
async def get_topic_trends(
    topic: str,
    days: int = Query(30, ge=1, le=365, description="天数")
):
    """
    获取主题趋势数据
    """
    logger.info("获取主题趋势", topic=topic, days=days)
    
    try:
        trend_data = await _get_topic_trends(topic, days)
        
        return {
            "topic": topic,
            "period_days": days,
            "trends": trend_data
        }
        
    except Exception as e:
        logger.error("获取趋势数据失败", topic=topic, error=str(e))
        raise HTTPException(status_code=500, detail=f"获取趋势数据失败: {str(e)}")


@router.get("/sentiment/{topic}")
async def get_topic_sentiment(
    topic: str,
    days: int = Query(7, ge=1, le=90, description="天数")
):
    """
    获取主题情感分析
    """
    logger.info("获取主题情感", topic=topic, days=days)
    
    try:
        sentiment = await _analyze_topic_sentiment(topic, days)
        
        return {
            "topic": topic,
            "period_days": days,
            "sentiment": sentiment,
            "analyzed_at": datetime.now()
        }
        
    except Exception as e:
        logger.error("情感分析失败", topic=topic, error=str(e))
        raise HTTPException(status_code=500, detail=f"情感分析失败: {str(e)}")


# 内部辅助函数
async def _generate_intelligence_report(request: AnalysisRequest) -> IntelligenceReport:
    """生成智能分析报告"""
    from app.services.intelligence_service import intelligence_service
    
    try:
        logger.info("开始生成智能分析报告", topic=request.topic, keywords=request.keywords)
        
        # 使用智能情报服务生成报告
        report_data = await intelligence_service.generate_intelligence_report(
            topic=request.topic,
            keywords=request.keywords,
            time_range=request.time_range,
            sources=request.sources
        )
        
        # 检查是否有错误
        if 'error' in report_data:
            logger.error("智能情报服务返回错误", error=report_data['error'])
            return _create_empty_report(request)
        
        # 转换为API响应格式
        end_date = datetime.now()
        start_date = end_date - timedelta(days=request.time_range)
        
        # 转换情感数据
        sentiment_data = report_data.get('sentiment', {})
        sentiment_score = sentiment_data.get('avg_score', 0.0)
        label_dist = sentiment_data.get('label_distribution', {})
        
        pos_ratio = label_dist.get('positive', {}).get('percentage', 0) / 100
        neg_ratio = label_dist.get('negative', {}).get('percentage', 0) / 100 
        neu_ratio = label_dist.get('neutral', {}).get('percentage', 0) / 100
        
        # 转换趋势数据
        trend_data = []
        for trend_point in report_data.get('trend_data', []):
            trend_data.append(TrendPoint(
                date=datetime.fromisoformat(trend_point['date']),
                value=trend_point['value'],
                volume=trend_point['volume']
            ))
        
        # 转换洞察数据
        key_insights = []
        for insight in report_data.get('key_insights', []):
            key_insights.append(KeyInsight(
                title=insight['title'],
                description=insight['description'],
                confidence=insight['confidence'],
                supporting_docs=insight.get('supporting_docs', [])
            ))
        
        # 构建最终报告
        report = IntelligenceReport(
            topic=request.topic,
            summary=report_data.get('summary', ''),
            sentiment=SentimentData(
                positive=pos_ratio,
                neutral=neu_ratio,
                negative=neg_ratio,
                score=sentiment_score
            ),
            trend_data=trend_data,
            key_insights=key_insights,
            related_topics=report_data.get('related_topics', []),
            generated_at=datetime.now(),
            data_period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": request.time_range,
                "total_documents": report_data.get('data_period', {}).get('total_documents', 0)
            }
        )
        
        logger.info("智能分析报告生成完成", 
                   topic=request.topic, 
                   documents_analyzed=report_data.get('data_period', {}).get('total_documents', 0),
                   sentiment_score=sentiment_score)
        
        return report
        
    except Exception as e:
        logger.error("智能分析报告生成失败", topic=request.topic, error=str(e))
        return _create_empty_report(request)


async def _search_relevant_documents(request: AnalysisRequest, start_date: datetime, end_date: datetime) -> List[dict]:
    """搜索相关文档"""
    from app.services.search_service import search_service
    
    try:
        # 构建查询字符串
        query_terms = [request.topic] + request.keywords
        query = " OR ".join(query_terms)
        
        # 构建时间过滤器
        filters = {
            "time_range": {
                "gte": start_date.isoformat(),
                "lte": end_date.isoformat()
            }
        }
        
        # 如果指定了数据源，添加过滤器
        if request.sources:
            filters["sources"] = request.sources
        
        # 执行混合搜索（关键词+语义）
        search_result = await search_service.search(
            query=query,
            search_type="hybrid",
            filters=filters,
            page=1,
            page_size=200,  # 获取更多文档用于分析
            sort_by="time"
        )
        
        documents = search_result.get("results", [])
        logger.info(f"搜索到 {len(documents)} 个相关文档", topic=request.topic)
        
        return documents
        
    except Exception as e:
        logger.error("搜索相关文档失败", topic=request.topic, error=str(e))
        return []


async def _generate_trend_data(documents: List[dict], start_date: datetime, end_date: datetime) -> List[TrendPoint]:
    """生成趋势数据"""
    try:
        from collections import defaultdict
        
        # 按日期分组文档
        daily_counts = defaultdict(int)
        daily_sentiment = defaultdict(list)
        
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
                
                # 简单的情感评分（基于标题关键词）
                title = doc.get("title", "")
                content = doc.get("content", "")
                text = title + " " + content
                
                # 简单情感评分
                sentiment_score = _calculate_simple_sentiment(text)
                daily_sentiment[date_key].append(sentiment_score)
                
            except Exception:
                continue
        
        # 生成趋势点
        trend_points = []
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            volume = daily_counts.get(current_date, 0)
            sentiments = daily_sentiment.get(current_date, [0])
            avg_sentiment = sum(sentiments) / len(sentiments)
            
            # 将情感分数转换为趋势值（50为基准）
            trend_value = 50 + avg_sentiment * 30 + (volume / 10)
            
            trend_points.append(TrendPoint(
                date=datetime.combine(current_date, datetime.min.time()),
                value=trend_value,
                volume=volume
            ))
            
            current_date += timedelta(days=1)
        
        logger.info(f"生成趋势数据 {len(trend_points)} 个数据点")
        return trend_points
        
    except Exception as e:
        logger.error("生成趋势数据失败", error=str(e))
        return []


def _calculate_simple_sentiment(text: str) -> float:
    """计算简单情感分数"""
    positive_words = {'涨', '增长', '上升', '利好', '好', '优', '强', '高', '升', '涨停'}
    negative_words = {'跌', '下降', '下跌', '利空', '差', '弱', '低', '跌停', '亏损', '风险'}
    
    pos_count = sum(1 for word in positive_words if word in text)
    neg_count = sum(1 for word in negative_words if word in text)
    
    if pos_count + neg_count == 0:
        return 0.0
    
    return (pos_count - neg_count) / (pos_count + neg_count)


async def _generate_key_insights(documents: List[dict], sentiment_results: List[dict], 
                                classification_results: List[dict], topic: str) -> List[KeyInsight]:
    """生成关键洞察"""
    insights = []
    
    try:
        # 1. 情感洞察
        if sentiment_results:
            pos_count = sum(1 for r in sentiment_results if r.get('label') == 'positive')
            neg_count = sum(1 for r in sentiment_results if r.get('label') == 'negative')
            total = len(sentiment_results)
            
            if pos_count > neg_count and pos_count / total > 0.6:
                insights.append(KeyInsight(
                    title="市场情绪积极",
                    description=f"针对{topic}的市场情绪整体积极，正面信息占比{pos_count/total:.1%}",
                    confidence=0.8,
                    supporting_docs=[doc.get('id', f'doc_{i}') for i, doc in enumerate(documents[:3])]
                ))
            elif neg_count > pos_count and neg_count / total > 0.6:
                insights.append(KeyInsight(
                    title="市场情绪偏谨慎",
                    description=f"针对{topic}的市场情绪偏谨慎，负面信息占比{neg_count/total:.1%}",
                    confidence=0.8,
                    supporting_docs=[doc.get('id', f'doc_{i}') for i, doc in enumerate(documents[:3])]
                ))
        
        # 2. 分类洞察
        if classification_results:
            # 统计新闻类型分布
            news_types = [r.get('news_type', {}).get('category') for r in classification_results]
            from collections import Counter
            type_counter = Counter(news_types)
            most_common_type = type_counter.most_common(1)
            
            if most_common_type:
                type_name, count = most_common_type[0]
                ratio = count / len(news_types)
                if ratio > 0.4:  # 如果某类型占比超过40%
                    insights.append(KeyInsight(
                        title=f"{type_name}信息集中",
                        description=f"{topic}相关信息中{type_name}类占主导地位（{ratio:.1%}），需要关注该领域动态",
                        confidence=0.7,
                        supporting_docs=[doc.get('id', f'doc_{i}') for i, doc in enumerate(documents[:5])]
                    ))
        
        # 3. 文档数量洞察
        doc_count = len(documents)
        if doc_count > 50:
            insights.append(KeyInsight(
                title="高关注度主题",
                description=f"{topic}获得了较高的市场关注度，共发现{doc_count}条相关信息",
                confidence=0.9,
                supporting_docs=[doc.get('id', f'doc_{i}') for i, doc in enumerate(documents[:10])]
            ))
        elif doc_count < 10:
            insights.append(KeyInsight(
                title="信息较少主题",
                description=f"{topic}相关信息较少（{doc_count}条），可能是新兴或小众领域",
                confidence=0.7,
                supporting_docs=[doc.get('id', f'doc_{i}') for i, doc in enumerate(documents)]
            ))
        
        logger.info(f"生成了 {len(insights)} 个关键洞察")
        return insights
        
    except Exception as e:
        logger.error("生成关键洞察失败", error=str(e))
        return []


async def _generate_related_topics(documents: List[dict], keywords: List[str]) -> List[str]:
    """生成相关主题"""
    try:
        from collections import Counter
        
        # 提取所有标题和内容中的关键词
        all_text = " ".join([doc.get("title", "") + " " + doc.get("content", "") for doc in documents])
        
        # 简单的关键词提取（实际项目中可以使用更复杂的NLP技术）
        import re
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text)  # 提取2个字符以上的中文词
        
        # 过滤掉原有关键词
        filtered_words = [word for word in words if word not in keywords]
        
        # 统计词频，取前10个
        word_counter = Counter(filtered_words)
        related_topics = [word for word, count in word_counter.most_common(10) if count >= 3]
        
        logger.info(f"生成了 {len(related_topics)} 个相关主题")
        return related_topics[:5]  # 返回前5个相关主题
        
    except Exception as e:
        logger.error("生成相关主题失败", error=str(e))
        return []


def _generate_summary(request: AnalysisRequest, sentiment_stats: dict, 
                     classification_stats: dict, doc_count: int) -> str:
    """生成分析摘要"""
    try:
        topic = request.topic
        time_range = request.time_range
        
        # 情感分析摘要
        avg_sentiment = sentiment_stats.get('avg_score', 0.0)
        if avg_sentiment > 0.2:
            sentiment_desc = "整体情感偏正面"
        elif avg_sentiment < -0.2:
            sentiment_desc = "整体情感偏负面"
        else:
            sentiment_desc = "整体情感中性"
        
        # 分类统计摘要
        news_dist = classification_stats.get('news_type_distribution', {})
        if news_dist:
            main_type = max(news_dist.items(), key=lambda x: x[1].get('count', 0))[0]
            type_desc = f"以{main_type}类信息为主"
        else:
            type_desc = "信息类型多样"
        
        summary = f"基于{time_range}天的数据分析，{topic}主题共收集到{doc_count}条相关信息，{sentiment_desc}，{type_desc}。"
        
        if avg_sentiment > 0.3:
            summary += "市场对该主题持积极态度，建议持续关注相关发展动态。"
        elif avg_sentiment < -0.3:
            summary += "市场对该主题存在担忧，需要谨慎关注风险因素。"
        else:
            summary += "市场对该主题态度相对理性，建议综合多方面因素进行判断。"
        
        return summary
        
    except Exception as e:
        logger.error("生成摘要失败", error=str(e))
        return f"针对{request.topic}的分析报告生成遇到问题，请稍后重试。"


def _create_empty_report(request: AnalysisRequest) -> IntelligenceReport:
    """创建空报告（当没有找到相关文档时）"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=request.time_range)
    
    return IntelligenceReport(
        topic=request.topic,
        summary=f"在指定的{request.time_range}天时间范围内，未找到与'{request.topic}'相关的足够信息。建议扩大时间范围或调整搜索关键词。",
        sentiment=SentimentData(
            positive=0.33,
            neutral=0.34,
            negative=0.33,
            score=0.0
        ),
        trend_data=[],
        key_insights=[
            KeyInsight(
                title="数据不足",
                description=f"当前时间范围内关于{request.topic}的信息较少，建议扩大搜索范围",
                confidence=0.9,
                supporting_docs=[]
            )
        ],
        related_topics=[],
        generated_at=datetime.now(),
        data_period={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": request.time_range,
            "total_documents": 0
        }
    )


async def _get_intelligence_reports(page: int, page_size: int, topic: Optional[str]):
    """获取智能分析报告列表"""
    # 实际实现会从数据库查询
    # 这里返回空列表，后续可以实现数据库存储
    return []


async def _save_monitoring_task(task: MonitoringTask):
    """保存监控任务"""
    # 实际实现会保存到数据库
    # 当前暂不实现持久化，后续可以添加数据库支持
    logger.info("监控任务已创建（内存中）", task_id=task.id, topic=task.topic)


async def _schedule_monitoring_job(task: MonitoringTask):
    """安排监控作业"""
    # 实际实现会配置Celery定时任务
    # 当前暂不实现，后续可以添加Celery支持
    logger.info("监控作业已调度（模拟）", task_id=task.id)


async def _get_monitoring_tasks():
    """获取监控任务列表"""
    # 实际实现会从数据库查询
    # 当前返回空列表
    return []


async def _get_topic_trends(topic: str, days: int):
    """获取主题趋势数据"""
    try:
        from app.services.search_service import search_service
        
        # 搜索指定主题的历史数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            "time_range": {
                "gte": start_date.isoformat(),
                "lte": end_date.isoformat()
            }
        }
        
        search_result = await search_service.search(
            query=topic,
            search_type="hybrid",
            filters=filters,
            page=1,
            page_size=100,
            sort_by="time"
        )
        
        documents = search_result.get("results", [])
        trend_data = await _generate_trend_data(documents, start_date, end_date)
        
        return [{"date": point.date.isoformat(), "value": point.value, "volume": point.volume} 
                for point in trend_data]
        
    except Exception as e:
        logger.error("获取主题趋势失败", topic=topic, error=str(e))
        return []


async def _analyze_topic_sentiment(topic: str, days: int):
    """分析主题情感"""
    try:
        from app.services.search_service import search_service
        import sys
        import os
        
        # 添加data-processor路径到Python路径
        data_processor_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data-processor')
        sys.path.append(data_processor_path)
        
        from nlp.sentiment_analysis import SentimentAnalyzer
        
        # 搜索相关文档
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            "time_range": {
                "gte": start_date.isoformat(),
                "lte": end_date.isoformat()
            }
        }
        
        search_result = await search_service.search(
            query=topic,
            search_type="hybrid",
            filters=filters,
            page=1,
            page_size=50,
            sort_by="relevance"
        )
        
        documents = search_result.get("results", [])
        
        if not documents:
            # 返回中性情感
            return SentimentData(
                positive=0.33,
                neutral=0.34,
                negative=0.33,
                score=0.0
            )
        
        # 执行情感分析
        sentiment_analyzer = SentimentAnalyzer(model_type="dictionary")
        texts = [doc.get("content", "") + " " + doc.get("title", "") for doc in documents]
        sentiment_results = sentiment_analyzer.batch_analyze(texts)
        sentiment_stats = sentiment_analyzer.get_sentiment_statistics(sentiment_results)
        
        # 返回统计结果
        avg_sentiment = sentiment_stats.get('avg_score', 0.0)
        pos_ratio = sentiment_stats.get('label_distribution', {}).get('positive', {}).get('percentage', 0) / 100
        neg_ratio = sentiment_stats.get('label_distribution', {}).get('negative', {}).get('percentage', 0) / 100
        neu_ratio = sentiment_stats.get('label_distribution', {}).get('neutral', {}).get('percentage', 0) / 100
        
        return SentimentData(
            positive=pos_ratio,
            neutral=neu_ratio,
            negative=neg_ratio,
            score=avg_sentiment
        )
        
    except Exception as e:
        logger.error("主题情感分析失败", topic=topic, error=str(e))
        return SentimentData(
            positive=0.33,
            neutral=0.34,
            negative=0.33,
            score=0.0
        )
