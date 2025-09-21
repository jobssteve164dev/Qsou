"""
系统监控和健康检查API端点
"""

from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from pathlib import Path
import structlog
import asyncio
import shutil

from app.services.search_service import search_service
from app.services.data_processing_service import data_processing_service
from app.core.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter()
@router.get("/stats")
async def system_stats():
    """
    提供给前端首页/监控页的系统统计信息（真实健康检查）。
    路径：/api/v1/system/stats
    """
    try:
        # 并行执行健康检查并记录耗时（暴露调试信息）
        es_health, es_ms = await _with_timeout_timed(
            search_service.elasticsearch.health_check(), 2.0, {"status": "timeout"}
        )
        qdrant_health, qdrant_ms = await _with_timeout_timed(
            search_service.qdrant.health_check(), 2.0, {"status": "timeout"}
        )
        processor_health, processor_ms = await _with_timeout_timed(
            data_processing_service.health_check(),
            2.0,
            {"healthy": False, "checks": {"celery": {"status": "unknown"}}},
        )
        crawler_ok, crawler_ms = await _with_timeout_timed(
            _check_crawler_service(), 1.0, False
        )

        elastic_ok = es_health.get("status") == "connected"
        qdrant_ok = qdrant_health.get("status") == "connected"
        processor_ok = bool(processor_health.get("healthy")) and (
            processor_health.get("checks", {}).get("celery", {}).get("status") == "healthy"
        )

        # 计算文档数量（在ES可用时）
        documents_count = 0
        if elastic_ok:
            try:
                index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}documents"
                client = search_service.elasticsearch.client
                if client:
                    count_resp = await _with_timeout(client.count(index=index_name), 1.5, {"count": 0})
                    documents_count = int(count_resp.get("count", 0))
            except Exception:
                documents_count = 0

        # 汇总系统状态
        service_ok_flags = [elastic_ok, qdrant_ok, bool(crawler_ok), processor_ok]
        if all(service_ok_flags):
            overall = "healthy"
        elif any(service_ok_flags):
            overall = "warning"
        else:
            overall = "error"

        # 生成服务异常消息（用于前端悬浮提示）
        def _es_msg():
            status = es_health.get("status")
            if status == "connected":
                return ""
            if status == "timeout":
                return "Elasticsearch 健康检查超时"
            return f"Elasticsearch 异常: {es_health.get('error', '未连接')}"

        def _q_msg():
            status = qdrant_health.get("status")
            if status == "connected":
                return ""
            if status == "timeout":
                return "Qdrant 健康检查超时"
            return f"Qdrant 异常: {qdrant_health.get('error', '未连接')}"

        def _p_msg():
            if processor_ok:
                return ""
            cel = processor_health.get("checks", {}).get("celery", {})
            if cel.get("status") == "no_workers":
                return "Celery 无可用 worker"
            if cel.get("status") == "unhealthy":
                return f"Celery 异常: {cel.get('error', '未知错误')}"
            return "数据处理服务未就绪"

        def _c_msg():
            if crawler_ok:
                return ""
            return "爬虫未就绪：缺少 scrapy 或日志过旧/未运行"

        payload = {
            "documents_count": documents_count,
            "searches_today": 0,
            "analysis_reports": 0,
            "system_status": overall,
            "services": {
                "elasticsearch": elastic_ok,
                "qdrant": qdrant_ok,
                "crawler": bool(crawler_ok),
                "processor": processor_ok,
            },
            "service_messages": {
                "elasticsearch": _es_msg(),
                "qdrant": _q_msg(),
                "crawler": _c_msg(),
                "processor": _p_msg(),
            },
            "diagnostics": {
                "durations_ms": {
                    "elasticsearch": es_ms,
                    "qdrant": qdrant_ms,
                    "processor": processor_ms,
                    "crawler": crawler_ms,
                },
                "raw": {
                    "elasticsearch": es_health,
                    "qdrant": qdrant_health,
                    "processor": processor_health,
                },
            },
        }
        logger.info(
            "系统统计诊断",
            es_ms=es_ms,
            qdrant_ms=qdrant_ms,
            processor_ms=processor_ms,
            crawler_ms=crawler_ms,
            es_status=es_health.get("status"),
            qdrant_status=qdrant_health.get("status"),
        )
        return payload
    except Exception as e:
        logger.error("系统统计获取失败", error=str(e))
        raise HTTPException(status_code=500, detail="系统统计获取失败")


class ServiceStatus(BaseModel):
    """服务状态模型"""
    name: str
    status: str  # healthy, unhealthy, unknown
    last_check: datetime
    response_time_ms: int
    message: str


class SystemHealth(BaseModel):
    """系统健康状态"""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    services: List[ServiceStatus]
    summary: dict


class SystemMetrics(BaseModel):
    """系统指标"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    request_rate: float
    error_rate: float
    avg_response_time: float


@router.get("/health", response_model=SystemHealth)
async def system_health_check():
    """
    系统整体健康检查
    检查所有关键服务的状态
    """
    logger.info("执行系统健康检查")
    
    try:
        # 检查各个服务的状态
        services = await _check_all_services()
        
        # 计算整体状态
        overall_status = _calculate_overall_status(services)
        
        # 生成摘要信息
        summary = _generate_health_summary(services)
        
        health = SystemHealth(
            status=overall_status,
            timestamp=datetime.now(),
            services=services,
            summary=summary
        )
        
        logger.info(
            "健康检查完成",
            status=overall_status,
            services_count=len(services)
        )
        
        return health
        
    except Exception as e:
        logger.error("健康检查失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.get("/metrics", response_model=SystemMetrics)
async def system_metrics():
    """
    获取系统性能指标
    """
    logger.info("获取系统指标")
    
    try:
        metrics = await _collect_system_metrics()
        
        logger.info("系统指标收集完成")
        return metrics
        
    except Exception as e:
        logger.error("指标收集失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"指标收集失败: {str(e)}")


@router.get("/services/{service_name}/health")
async def service_health_check(service_name: str):
    """
    单个服务健康检查
    """
    logger.info("检查服务健康", service=service_name)
    
    try:
        service_status = await _check_service_health(service_name)
        
        if not service_status:
            raise HTTPException(status_code=404, detail="服务不存在")
        
        logger.info(
            "服务健康检查完成",
            service=service_name,
            status=service_status.status
        )
        
        return service_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("服务健康检查失败", service=service_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"服务健康检查失败: {str(e)}")


@router.get("/status/database")
async def database_status():
    """
    数据库状态检查
    """
    logger.info("检查数据库状态")
    
    try:
        # TODO: 实现真实的数据库连接检查
        # from app.core.database import check_database_connection
        # is_connected = await check_database_connection()
        
        # 模拟数据库检查
        is_connected = True
        response_time = 25  # ms
        
        status = {
            "service": "PostgreSQL",
            "connected": is_connected,
            "response_time_ms": response_time,
            "pool_status": {
                "active_connections": 5,
                "max_connections": 20,
                "idle_connections": 15
            },
            "last_check": datetime.now()
        }
        
        logger.info("数据库状态检查完成", connected=is_connected)
        return status
        
    except Exception as e:
        logger.error("数据库状态检查失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"数据库状态检查失败: {str(e)}")


@router.get("/status/redis")
async def redis_status():
    """
    Redis状态检查
    """
    logger.info("检查Redis状态")
    
    try:
        # TODO: 实现真实的Redis连接检查
        # import redis
        # redis_client = redis.from_url(settings.REDIS_URL)
        # redis_client.ping()
        
        # 模拟Redis检查
        status = {
            "service": "Redis",
            "connected": True,
            "response_time_ms": 12,
            "memory_usage": "128MB",
            "connected_clients": 8,
            "keyspace": {
                "db0": {"keys": 1250, "expires": 450}
            },
            "last_check": datetime.now()
        }
        
        logger.info("Redis状态检查完成")
        return status
        
    except Exception as e:
        logger.error("Redis状态检查失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"Redis状态检查失败: {str(e)}")


@router.get("/status/elasticsearch")
async def elasticsearch_status():
    """
    Elasticsearch状态检查
    """
    logger.info("检查Elasticsearch状态")
    
    try:
        # TODO: 实现真实的Elasticsearch连接检查
        # from elasticsearch import AsyncElasticsearch
        # es = AsyncElasticsearch([f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"])
        # cluster_health = await es.cluster.health()
        
        # 模拟Elasticsearch检查
        status = {
            "service": "Elasticsearch",
            "connected": True,
            "response_time_ms": 45,
            "cluster_status": "green",
            "nodes_count": 1,
            "indices_count": 5,
            "documents_count": 12500,
            "storage_size": "2.3GB",
            "last_check": datetime.now()
        }
        
        logger.info("Elasticsearch状态检查完成")
        return status
        
    except Exception as e:
        logger.error("Elasticsearch状态检查失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"Elasticsearch状态检查失败: {str(e)}")


@router.get("/status/qdrant")
async def qdrant_status():
    """
    Qdrant向量数据库状态检查
    """
    logger.info("检查Qdrant状态")
    
    try:
        # TODO: 实现真实的Qdrant连接检查
        # from qdrant_client import QdrantClient
        # qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        # collections = qdrant.get_collections()
        
        # 模拟Qdrant检查
        status = {
            "service": "Qdrant",
            "connected": True,
            "response_time_ms": 18,
            "collections": [
                {
                    "name": "investment_documents",
                    "vectors_count": 8500,
                    "indexed_vectors": 8500,
                    "dimension": 768
                }
            ],
            "memory_usage": "512MB",
            "last_check": datetime.now()
        }
        
        logger.info("Qdrant状态检查完成")
        return status
        
    except Exception as e:
        logger.error("Qdrant状态检查失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"Qdrant状态检查失败: {str(e)}")


# 内部辅助函数
async def _check_all_services() -> List[ServiceStatus]:
    """检查所有服务状态"""
    
    services_to_check = [
        ("database", _check_database),
        ("redis", _check_redis), 
        ("elasticsearch", _check_elasticsearch),
        ("qdrant", _check_qdrant),
        ("celery", _check_celery)
    ]
    
    services = []
    
    # 并行检查所有服务
    tasks = [check_func() for _, check_func in services_to_check]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for (service_name, _), result in zip(services_to_check, results):
        if isinstance(result, Exception):
            services.append(ServiceStatus(
                name=service_name,
                status="unhealthy",
                last_check=datetime.now(),
                response_time_ms=0,
                message=f"检查失败: {str(result)}"
            ))
        else:
            services.append(result)
    
    return services


async def _check_service_health(service_name: str) -> ServiceStatus:
    """检查指定服务健康状态"""
    
    check_functions = {
        "database": _check_database,
        "redis": _check_redis,
        "elasticsearch": _check_elasticsearch,
        "qdrant": _check_qdrant,
        "celery": _check_celery
    }
    
    check_func = check_functions.get(service_name)
    if not check_func:
        return None
    
    return await check_func()


async def _check_database() -> ServiceStatus:
    """检查数据库状态"""
    start_time = datetime.now()
    
    try:
        # TODO: 实现真实的数据库检查
        # from app.core.database import check_database_connection
        # is_healthy = await check_database_connection()
        
        is_healthy = True  # 模拟
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return ServiceStatus(
            name="database",
            status="healthy" if is_healthy else "unhealthy",
            last_check=datetime.now(),
            response_time_ms=response_time,
            message="数据库连接正常" if is_healthy else "数据库连接失败"
        )
        
    except Exception as e:
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return ServiceStatus(
            name="database",
            status="unhealthy",
            last_check=datetime.now(),
            response_time_ms=response_time,
            message=f"数据库检查异常: {str(e)}"
        )


async def _check_redis() -> ServiceStatus:
    """检查Redis状态"""
    return ServiceStatus(
        name="redis",
        status="healthy",
        last_check=datetime.now(),
        response_time_ms=12,
        message="Redis连接正常"
    )


async def _check_elasticsearch() -> ServiceStatus:
    """检查Elasticsearch状态"""
    return ServiceStatus(
        name="elasticsearch", 
        status="healthy",
        last_check=datetime.now(),
        response_time_ms=45,
        message="Elasticsearch集群状态正常"
    )


async def _check_qdrant() -> ServiceStatus:
    """检查Qdrant状态"""
    return ServiceStatus(
        name="qdrant",
        status="healthy",
        last_check=datetime.now(),
        response_time_ms=18,
        message="Qdrant向量数据库正常"
    )


async def _check_celery() -> ServiceStatus:
    """检查Celery状态"""
    return ServiceStatus(
        name="celery",
        status="healthy", 
        last_check=datetime.now(),
        response_time_ms=30,
        message="Celery任务队列正常"
    )


def _calculate_overall_status(services: List[ServiceStatus]) -> str:
    """计算整体系统状态"""
    unhealthy_count = sum(1 for s in services if s.status == "unhealthy")
    
    if unhealthy_count == 0:
        return "healthy"
    elif unhealthy_count < len(services) // 2:
        return "degraded"
    else:
        return "unhealthy"


def _generate_health_summary(services: List[ServiceStatus]) -> dict:
    """生成健康状况摘要"""
    healthy = sum(1 for s in services if s.status == "healthy")
    unhealthy = sum(1 for s in services if s.status == "unhealthy")
    
    return {
        "total_services": len(services),
        "healthy_services": healthy,
        "unhealthy_services": unhealthy,
        "avg_response_time_ms": sum(s.response_time_ms for s in services) // len(services) if services else 0
    }


async def _collect_system_metrics() -> SystemMetrics:
    """收集系统性能指标"""
    # TODO: 实现真实的系统指标收集
    # 使用psutil等库收集系统指标
    
    # 模拟数据
    return SystemMetrics(
        cpu_usage=25.5,
        memory_usage=68.2,
        disk_usage=45.8,
        active_connections=156,
        request_rate=42.5,
        error_rate=0.15,
        avg_response_time=125.8
    )


async def _check_crawler_service() -> bool:
    """检查爬虫服务健康状况。
    判定标准（尽量避免臆测，基于可观测事实）：
    1) Celery worker 可用（由数据处理服务健康检查提供）
    2) 存在 Scrapy 项目结构（crawler/scrapy.cfg）
    3) 二者其一满足：
       - 系统中可找到 scrapy 可执行文件；或
       - 爬虫日志在最近24小时内有更新。
    """
    try:
        # 1) Celery 健康
        processor_health = await data_processing_service.health_check()
        celery_ok = processor_health.get("checks", {}).get("celery", {}).get("status") == "healthy"

        # 2) Scrapy 项目结构与日志
        api_gateway_dir = Path(__file__).resolve().parents[4]
        project_root = api_gateway_dir.parent
        crawler_dir = project_root / "crawler"
        cfg_ok = (crawler_dir / "scrapy.cfg").exists()

        # 3) scrapy 可执行 或 日志最近更新
        scrapy_ok = shutil.which("scrapy") is not None
        log_file = crawler_dir / "logs" / "scrapy.log"
        recent_log = False
        if log_file.exists():
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                recent_log = (datetime.now() - mtime) <= timedelta(hours=24)
            except Exception:
                recent_log = False

        return bool(celery_ok and cfg_ok and (scrapy_ok or recent_log))
    except Exception:
        return False


async def _with_timeout(coro, seconds: float, fallback):
    """为协程执行设置超时，超时/异常时返回给定回退值。"""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except Exception:
        return fallback


async def _with_timeout_timed(coro, seconds: float, fallback):
    """带耗时统计的超时包装，返回 (结果, 毫秒)。"""
    import time
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(coro, timeout=seconds)
        return result, int((time.monotonic() - start) * 1000)
    except Exception:
        return fallback, int((time.monotonic() - start) * 1000)
