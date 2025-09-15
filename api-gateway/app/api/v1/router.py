"""
API v1 主路由
"""

from fastapi import APIRouter

from app.api.v1.endpoints import search, documents, intelligence, health

api_router = APIRouter()

# 注册子路由
api_router.include_router(
    search.router, 
    prefix="/search", 
    tags=["搜索引擎"]
)

api_router.include_router(
    documents.router, 
    prefix="/documents", 
    tags=["文档管理"]
)

api_router.include_router(
    intelligence.router, 
    prefix="/intelligence", 
    tags=["智能分析"]
)

api_router.include_router(
    health.router, 
    prefix="/system", 
    tags=["系统监控"]
)
