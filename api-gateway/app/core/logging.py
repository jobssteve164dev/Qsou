"""
结构化日志配置
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
import structlog
from pathlib import Path

from app.core.config import settings


def setup_logging():
    """设置结构化日志"""
    
    # 确保日志目录存在
    log_dir = Path("../logs")
    log_dir.mkdir(exist_ok=True)
    
    # 暂时硬编码日志路径以避免环境变量解析问题
    log_file_path = "../logs/app.log"
    
    # 配置标准库日志
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.handlers.RotatingFileHandler(
                log_file_path,
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=5,
                encoding="utf-8"
            )
        ]
    )
    
    # 配置structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # 设置外部库的日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)


def get_logger(name: str):
    """获取结构化日志器"""
    return structlog.get_logger(name)
