"""
Qsou Investment Intelligence Engine - API Gateway
主应用程序入口点
"""

import os
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Windows环境设置UTF-8编码
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn
import logging
from datetime import datetime, timezone

from app.core.config import settings
# from app.core.database import engine, create_tables
from app.core.logging import setup_logging
from app.api.v1.router import api_router
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.services.search_service import search_service
from app.services.data_processing_service import data_processing_service
from qsou_data.migration_state import migration_state

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时执行
    logger.info("🚀 启动 Qsou 自主投资数据服务")
    logger.info(f"🔧 环境: {settings.ENVIRONMENT}")
    logger.info(f"🐛 调试模式: {settings.DEBUG}")
    
    # 创建数据库表 - 暂时禁用
    # await create_tables()
    # logger.info("📊 数据库表初始化完成")
    
    # 连接外部服务
    try:
        # 初始化已配置的可重建搜索服务。
        search_initialized = await search_service.initialize()
        if search_initialized:
            logger.info("🔍 搜索服务初始化成功")
        else:
            logger.warning("⚠️  搜索服务初始化失败，部分功能可能不可用")
        
        # 可选派生处理不影响原始证据与标准文档落地。
        if settings.ENABLE_DERIVED_PROCESSING:
            try:
                data_processing_status = await data_processing_service.get_status()
                if data_processing_status.get("status") == "running":
                    logger.info("📊 派生数据处理服务初始化成功")
                else:
                    logger.warning("⚠️  派生数据处理服务未就绪")
            except Exception as e:
                logger.warning(f"⚠️  派生数据处理服务检查失败: {e}")
        else:
            logger.info("📊 派生数据处理未启用，标准文档保留在可靠待处理队列")
        
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
    title="Qsou 自主投资数据 API",
    description="采集、保存、搜索和导出自己掌握的投资数据",
    version="0.2.0",
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


@app.middleware("http")
async def migration_write_gate(request, call_next):
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and request.url.path != "/api/v1/auth/login"
    ):
        state = migration_state(search_service.data_assets)
        if state["status"] != "ready":
            return JSONResponse(
                status_code=503,
                content={"detail": "数据升级正在完成，请稍后重试"},
            )
    return await call_next(request)

# 注册路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径 - 系统状态检查"""
    return {
        "service": "Qsou 自主投资数据 API",
        "version": "0.2.0",
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": [
            "来源登记",
            "原始证据归档",
            "自有数据搜索",
            "开放格式导出"
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
        
        overall_status = search_health.get("status", "unhealthy")
        
        payload = {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "data_assets": search_health.get("data_assets"),
                "search_engine": search_health
            }
        }
        if overall_status != "healthy":
            return JSONResponse(status_code=503, content=payload)
        return payload
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/live")
async def liveness_check():
    """Process liveness for staged GitOps rollout; readiness remains on /health."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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
