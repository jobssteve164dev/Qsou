"""
性能指标收集中间件
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge
import structlog

logger = structlog.get_logger(__name__)

# Prometheus指标定义
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Number of active HTTP requests'
)

REQUEST_SIZE = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint']
)

RESPONSE_SIZE = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint']
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """性能指标收集中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """收集请求性能指标"""
        
        # 增加活跃请求计数
        ACTIVE_REQUESTS.inc()
        
        # 记录开始时间
        start_time = time.time()
        
        # 获取请求大小
        request_size = int(request.headers.get("content-length", 0))
        
        # 获取路径模板（去除具体参数）
        endpoint = self._get_endpoint_template(request)
        method = request.method
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            duration = time.time() - start_time
            
            # 获取响应大小
            response_size = 0
            if hasattr(response, 'body'):
                response_size = len(response.body)
            
            # 记录指标
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            REQUEST_SIZE.labels(
                method=method,
                endpoint=endpoint
            ).observe(request_size)
            
            RESPONSE_SIZE.labels(
                method=method,
                endpoint=endpoint
            ).observe(response_size)
            
            return response
            
        except Exception as exc:
            # 记录异常指标
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=500
            ).inc()
            
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            raise
        finally:
            # 减少活跃请求计数
            ACTIVE_REQUESTS.dec()
    
    def _get_endpoint_template(self, request: Request) -> str:
        """获取端点模板路径"""
        # 简化版本，实际项目中可能需要更复杂的路径模板提取
        path = request.url.path
        
        # 常见的模板化处理
        if "/api/v1/" in path:
            parts = path.split("/")
            if len(parts) > 4:
                # 处理类似 /api/v1/documents/{id} 的路径
                if parts[4].isdigit() or len(parts[4]) > 10:
                    parts[4] = "{id}"
            return "/".join(parts)
        
        return path
