"""
搜索引擎API端点
实现全文搜索和语义搜索功能
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from datetime import datetime
import structlog

from app.services.search_service import search_service

logger = structlog.get_logger(__name__)
router = APIRouter()


# Pydantic模型定义
class SearchQuery(BaseModel):
    """搜索查询模型"""
    query: str = Field(..., description="搜索关键词", min_length=1, max_length=200)
    search_type: str = Field(default="hybrid", description="搜索类型: keyword, semantic, hybrid")
    filters: Optional[dict] = Field(default=None, description="搜索过滤器")
    page: int = Field(default=1, description="页码", ge=1)
    page_size: int = Field(default=20, description="每页结果数", ge=1, le=100)
    sort_by: str = Field(default="relevance", description="排序方式: relevance, time, popularity")


class SearchResult(BaseModel):
    """搜索结果项"""
    id: str = Field(..., description="文档ID")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="内容摘要")
    source: str = Field(..., description="数据源")
    url: Optional[str] = Field(None, description="原始URL")
    published_at: datetime = Field(..., description="发布时间")
    relevance_score: float = Field(..., description="相关性得分", ge=0.0, le=1.0)
    tags: List[str] = Field(default=[], description="标签列表")


class SearchResponse(BaseModel):
    """搜索响应模型"""
    query: str = Field(..., description="搜索查询")
    total_count: int = Field(..., description="总结果数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    results: List[SearchResult] = Field(..., description="搜索结果")
    search_time_ms: int = Field(..., description="搜索耗时(毫秒)")
    suggestions: List[str] = Field(default=[], description="搜索建议")


@router.post("/", response_model=SearchResponse)
async def search_documents(search_query: SearchQuery):
    """
    执行文档搜索
    支持全文搜索、语义搜索和混合搜索
    """
    start_time = datetime.now()
    
    logger.info(
        "执行搜索",
        query=search_query.query,
        search_type=search_query.search_type,
        page=search_query.page
    )
    
    try:
        # 使用真实的搜索服务
        search_result = await search_service.search(
            query=search_query.query,
            search_type=search_query.search_type,
            filters=search_query.filters,
            page=search_query.page,
            page_size=search_query.page_size,
            sort_by=search_query.sort_by
        )
        
        # 获取搜索建议
        suggestions = await search_service.get_suggestions(search_query.query)
        
        response = SearchResponse(
            query=search_query.query,
            total_count=search_result["total_count"],
            page=search_query.page,
            page_size=search_query.page_size,
            results=search_result["results"],
            search_time_ms=search_result["search_time_ms"],
            suggestions=suggestions
        )
        
        logger.info(
            "搜索完成",
            query=search_query.query,
            total_results=response.total_count,
            search_time_ms=response.search_time_ms
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "搜索失败",
            query=search_query.query,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"搜索服务异常: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., description="查询关键词", min_length=1)
):
    """
    获取搜索建议
    """
    logger.info("获取搜索建议", query=q)
    
    try:
        suggestions = await search_service.get_suggestions(q)
        return {"query": q, "suggestions": suggestions}
        
    except Exception as e:
        logger.error("获取搜索建议失败", query=q, error=str(e))
        raise HTTPException(status_code=500, detail="无法获取搜索建议")


@router.get("/trending")
async def get_trending_searches():
    """
    获取热门搜索关键词
    """
    logger.info("获取热门搜索")
    
    try:
        # TODO: 实现基于真实数据的热门搜索统计
        trending = [
            {"keyword": "新能源汽车", "count": 1250},
            {"keyword": "人工智能", "count": 980},
            {"keyword": "芯片半导体", "count": 856},
            {"keyword": "医疗健康", "count": 743},
            {"keyword": "金融科技", "count": 621},
        ]
        
        return {"trending_searches": trending}
        
    except Exception as e:
        logger.error("获取热门搜索失败", error=str(e))
        raise HTTPException(status_code=500, detail="无法获取热门搜索")


@router.get("/similar/{document_id}")
async def get_similar_documents(
    document_id: str,
    limit: int = Query(default=10, description="返回结果数量", ge=1, le=50)
):
    """
    获取相似文档
    基于向量相似度查找与指定文档相似的其他文档
    """
    logger.info("查找相似文档", document_id=document_id, limit=limit)
    
    try:
        similar_docs = await search_service.find_similar_documents(
            document_id=document_id,
            limit=limit
        )
        
        return {
            "document_id": document_id,
            "similar_documents": similar_docs,
            "count": len(similar_docs)
        }
        
    except Exception as e:
        logger.error("查找相似文档失败", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail="无法查找相似文档")


