"""
Qsou Investment Intelligence Engine - API Gateway
主应用程序入口点
"""

import os
import sys
# Windows环境设置UTF-8编码
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn
import logging
from datetime import datetime

from app.core.config import settings
# from app.core.database import engine, create_tables
from app.core.logging import setup_logging
from app.api.v1.router import api_router
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.services.search_service import search_service

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时执行
    logger.info("🚀 启动 Qsou Investment Intelligence Engine API Gateway")
    logger.info(f"🔧 环境: {settings.ENVIRONMENT}")
    logger.info(f"🐛 调试模式: {settings.DEBUG}")
    
    # 创建数据库表 - 暂时禁用
    # await create_tables()
    # logger.info("📊 数据库表初始化完成")
    
    # 连接外部服务
    try:
        # 初始化搜索服务（Elasticsearch + Qdrant）
        search_initialized = await search_service.initialize()
        if search_initialized:
            logger.info("🔍 搜索服务初始化成功")
        else:
            logger.warning("⚠️  搜索服务初始化失败，部分功能可能不可用")
        
        # TODO: 在这里初始化Redis连接
        logger.info("🔗 外部服务连接检查完成")
    except Exception as e:
        logger.error(f"❌ 外部服务连接失败: {e}")
    
    yield
    
    # 关闭时执行
    logger.info("🛑 正在关闭 API Gateway...")
    
    # 关闭搜索服务
    await search_service.shutdown()


# 创建FastAPI应用
app = FastAPI(
    title="Qsou Investment Intelligence Engine API",
    description="自部署的投资情报搜索引擎 - 为量化交易提供实时数据源",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# 添加中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestLoggingMiddleware)

if settings.ENABLE_METRICS:
    app.add_middleware(MetricsMiddleware)

# 注册路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径 - 系统状态检查"""
    return {
        "service": "Qsou Investment Intelligence Engine API Gateway",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "features": [
            "🔍 实时金融数据搜索",
            "🤖 智能情报分析",
            "📊 向量化知识库",
            "⚡ 高性能API接口"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 检查搜索服务
        search_health = await search_service.health_check()
        
        # 检查数据库连接
        # TODO: 添加Redis连接检查
        
        # 判断整体健康状态
        overall_status = "healthy" if search_health.get("status") == "healthy" else "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "connected",
                "redis": "checking...",
                "search_engine": search_health
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/metrics")
async def metrics():
    """系统指标端点"""
    if not settings.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    # TODO: 实现详细的系统指标收集
    return {
        "requests_total": "TODO",
        "response_time_avg": "TODO",
        "active_connections": "TODO",
        "database_connections": "TODO"
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        workers=settings.API_WORKERS if not settings.API_RELOAD else 1,
        log_level="info",
        access_log=settings.API_ACCESS_LOG,
    )
