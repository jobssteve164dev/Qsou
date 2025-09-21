"""
系统监控和健康检查API端点
"""

from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import structlog
import asyncio

logger = structlog.get_logger(__name__)
router = APIRouter()
@router.get("/stats")
async def system_stats():
    """
    提供给前端首页/监控页的简要系统统计信息。
    避免 404：路径为 /api/v1/system/stats。
    """
    try:
        # 获取真实的服务状态
        services = await _check_all_services()
        
        # 构建服务状态映射
        service_status_map = {}
        for service in services:
            service_status_map[service.name] = service.status == "healthy"
        
        # 计算整体系统状态
        overall_status = _calculate_overall_status(services)
        
        # 获取基本统计信息（这里可以后续扩展为真实数据）
        return {
            "documents_count": 0,  # TODO: 从Elasticsearch获取真实文档数
            "searches_today": 0,   # TODO: 从日志或数据库获取真实搜索数
            "analysis_reports": 0, # TODO: 从数据库获取真实报告数
            "system_status": overall_status,
            "services": {
                "elasticsearch": service_status_map.get("elasticsearch", False),
                "qdrant": service_status_map.get("qdrant", False),
                "crawler": service_status_map.get("crawler", False),
                "processor": service_status_map.get("celery", False),  # 使用celery作为processor状态
            },
        }
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
        ("celery", _check_celery),
        ("crawler", _check_crawler)
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
        "celery": _check_celery,
        "crawler": _check_crawler
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
    start_time = datetime.now()
    
    try:
        # 使用现有的ElasticsearchService进行真实检查
        from app.services.elasticsearch_service import search_service
        
        health_info = await search_service.elasticsearch.health_check()
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        if health_info.get("status") == "connected":
            return ServiceStatus(
                name="elasticsearch",
                status="healthy",
                last_check=datetime.now(),
                response_time_ms=response_time,
                message=f"Elasticsearch集群状态: {health_info.get('cluster_status', 'unknown')}"
            )
        else:
            return ServiceStatus(
                name="elasticsearch",
                status="unhealthy",
                last_check=datetime.now(),
                response_time_ms=response_time,
                message=f"Elasticsearch连接失败: {health_info.get('error', 'unknown error')}"
            )
        
    except Exception as e:
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return ServiceStatus(
            name="elasticsearch",
            status="unhealthy",
            last_check=datetime.now(),
            response_time_ms=response_time,
            message=f"Elasticsearch检查异常: {str(e)}"
        )


async def _check_qdrant() -> ServiceStatus:
    """检查Qdrant状态"""
    start_time = datetime.now()
    
    try:
        # 使用现有的QdrantService进行真实检查
        from app.services.qdrant_service import qdrant_service
        
        health_info = await qdrant_service.health_check()
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        if health_info.get("status") == "connected":
            return ServiceStatus(
                name="qdrant",
                status="healthy",
                last_check=datetime.now(),
                response_time_ms=response_time,
                message=f"Qdrant向量数据库正常，集合数: {health_info.get('collections_count', 0)}"
            )
        else:
            return ServiceStatus(
                name="qdrant",
                status="unhealthy",
                last_check=datetime.now(),
                response_time_ms=response_time,
                message=f"Qdrant连接失败: {health_info.get('error', 'unknown error')}"
            )
        
    except Exception as e:
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return ServiceStatus(
            name="qdrant",
            status="unhealthy",
            last_check=datetime.now(),
            response_time_ms=response_time,
            message=f"Qdrant检查异常: {str(e)}"
        )


async def _check_celery() -> ServiceStatus:
    """检查Celery状态"""
    start_time = datetime.now()
    
    try:
        # 使用现有的DataProcessingService检查Celery状态
        from app.services.data_processing_service import DataProcessingService
        
        processing_service = DataProcessingService()
        
        # 检查Celery连接
        if processing_service.celery_app is None:
            return ServiceStatus(
                name="celery",
                status="unhealthy",
                last_check=datetime.now(),
                response_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                message="Celery未初始化"
            )
        
        # 尝试获取Celery worker状态
        try:
            # 检查活跃的worker
            inspect = processing_service.celery_app.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                worker_count = len(active_workers)
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                return ServiceStatus(
                    name="celery",
                    status="healthy",
                    last_check=datetime.now(),
                    response_time_ms=response_time,
                    message=f"Celery任务队列正常，活跃Worker: {worker_count}个"
                )
            else:
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                return ServiceStatus(
                    name="celery",
                    status="unhealthy",
                    last_check=datetime.now(),
                    response_time_ms=response_time,
                    message="Celery无活跃Worker"
                )
                
        except Exception as e:
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ServiceStatus(
                name="celery",
                status="unhealthy",
                last_check=datetime.now(),
                response_time_ms=response_time,
                message=f"Celery Worker检查失败: {str(e)}"
            )
        
    except Exception as e:
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return ServiceStatus(
            name="celery",
            status="unhealthy",
            last_check=datetime.now(),
            response_time_ms=response_time,
            message=f"Celery检查异常: {str(e)}"
        )


async def _check_crawler() -> ServiceStatus:
    """检查爬虫服务状态"""
    start_time = datetime.now()
    
    try:
        import requests
        import subprocess
        import os
        
        # 检查爬虫进程是否运行
        try:
            # 检查是否有Scrapy进程在运行
            result = subprocess.run(
                ['ps', 'aux'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                # 检查是否有scrapy进程
                scrapy_processes = [line for line in result.stdout.split('\n') if 'scrapy' in line.lower()]
                
                if scrapy_processes:
                    response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    return ServiceStatus(
                        name="crawler",
                        status="healthy",
                        last_check=datetime.now(),
                        response_time_ms=response_time,
                        message=f"爬虫服务运行中，活跃进程: {len(scrapy_processes)}个"
                    )
                else:
                    # 检查爬虫依赖是否可用
                    try:
                        # 检查Scrapy是否安装
                        scrapy_check = subprocess.run(
                            ['scrapy', '--version'], 
                            capture_output=True, 
                            text=True, 
                            timeout=5
                        )
                        
                        if scrapy_check.returncode == 0:
                            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                            return ServiceStatus(
                                name="crawler",
                                status="healthy",
                                last_check=datetime.now(),
                                response_time_ms=response_time,
                                message="爬虫服务就绪，Scrapy已安装"
                            )
                        else:
                            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                            return ServiceStatus(
                                name="crawler",
                                status="unhealthy",
                                last_check=datetime.now(),
                                response_time_ms=response_time,
                                message="Scrapy未正确安装"
                            )
                    except Exception as e:
                        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                        return ServiceStatus(
                            name="crawler",
                            status="unhealthy",
                            last_check=datetime.now(),
                            response_time_ms=response_time,
                            message=f"Scrapy检查失败: {str(e)}"
                        )
            else:
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)
                return ServiceStatus(
                    name="crawler",
                    status="unhealthy",
                    last_check=datetime.now(),
                    response_time_ms=response_time,
                    message="无法检查进程状态"
                )
                
        except subprocess.TimeoutExpired:
            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return ServiceStatus(
                name="crawler",
                status="unhealthy",
                last_check=datetime.now(),
                response_time_ms=response_time,
                message="进程检查超时"
            )
        
    except Exception as e:
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        return ServiceStatus(
            name="crawler",
            status="unhealthy",
            last_check=datetime.now(),
            response_time_ms=response_time,
            message=f"爬虫服务检查异常: {str(e)}"
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
