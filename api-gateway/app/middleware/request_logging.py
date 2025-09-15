"""
请求日志中间件
记录所有API请求和响应的详细信息
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志记录中间件"""
    
    def __init__(self, app, exclude_paths: set = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or {"/health", "/metrics"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        
        # 生成请求ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 记录请求开始时间
        start_time = time.time()
        
        # 获取客户端IP
        client_ip = request.headers.get("x-forwarded-for", request.client.host)
        
        # 跳过某些路径的日志记录
        if request.url.path not in self.exclude_paths:
            logger.info(
                "请求开始",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params),
                client_ip=client_ip,
                user_agent=request.headers.get("user-agent"),
            )
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算响应时间
            process_time = time.time() - start_time
            
            # 记录响应日志
            if request.url.path not in self.exclude_paths:
                logger.info(
                    "请求完成",
                    request_id=request_id,
                    status_code=response.status_code,
                    process_time=f"{process_time:.3f}s",
                )
            
            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as exc:
            # 记录异常
            process_time = time.time() - start_time
            logger.error(
                "请求异常",
                request_id=request_id,
                exception=str(exc),
                process_time=f"{process_time:.3f}s",
            )
            raise
