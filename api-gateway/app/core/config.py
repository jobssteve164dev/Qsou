"""
应用配置管理
从环境变量和配置文件加载设置
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator
from functools import lru_cache


class Settings(BaseSettings):
    """应用设置类"""
    
    # 基础配置
    PROJECT_NAME: str = Field(default="Qsou Investment Intelligence Engine", env="PROJECT_NAME")
    PROJECT_VERSION: str = Field(default="1.0.0", env="PROJECT_VERSION")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")
    
    # API服务配置
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_WORKERS: int = Field(default=1, env="API_WORKERS")
    API_RELOAD: bool = Field(default=True, env="API_RELOAD")
    API_ACCESS_LOG: bool = Field(default=True, env="API_ACCESS_LOG")
    
    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql://qsou:your_password@localhost:5432/qsou_investment_intel", 
        env="DATABASE_URL"
    )
    
    # Redis配置
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    
    # Elasticsearch配置
    ELASTICSEARCH_HOST: str = Field(default="localhost", env="ELASTICSEARCH_HOST")
    ELASTICSEARCH_PORT: int = Field(default=9200, env="ELASTICSEARCH_PORT")
    ELASTICSEARCH_INDEX_PREFIX: str = Field(default="qsou_", env="ELASTICSEARCH_INDEX_PREFIX")
    
    # Qdrant配置
    QDRANT_HOST: str = Field(default="localhost", env="QDRANT_HOST")
    QDRANT_PORT: int = Field(default=6333, env="QDRANT_PORT")
    QDRANT_COLLECTION_NAME: str = Field(default="investment_documents", env="QDRANT_COLLECTION_NAME")
    
    # 安全配置
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # CORS配置
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"], 
        env="CORS_ORIGINS"
    )
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_DIR: str = Field(default="logs", env="LOG_DIR")
    LOG_FILE: str = Field(default="logs/app.log", env="LOG_FILE")
    
    # 性能配置
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    HEALTH_CHECK_INTERVAL: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    SERVICE_TIMEOUT: int = Field(default=60, env="SERVICE_TIMEOUT")
    
    # NLP & AI配置
    BERT_MODEL_PATH: str = Field(default="bert-base-chinese", env="BERT_MODEL_PATH")
    SENTENCE_TRANSFORMER_MODEL: str = Field(
        default="shibing624/text2vec-base-chinese", 
        env="SENTENCE_TRANSFORMER_MODEL"
    )
    EMBEDDING_DIMENSION: int = Field(default=768, env="EMBEDDING_DIMENSION")
    MAX_SEQUENCE_LENGTH: int = Field(default=512, env="MAX_SEQUENCE_LENGTH")
    
    # 爬虫配置
    SPIDER_USER_AGENT: str = Field(
        default="Qsou-InvestmentBot/1.0 (+http://your-domain.com/bot; contact@your-domain.com)",
        env="SPIDER_USER_AGENT"
    )
    DOWNLOAD_DELAY: float = Field(default=1.0, env="DOWNLOAD_DELAY")
    SPIDER_CONCURRENCY: int = Field(default=8, env="SPIDER_CONCURRENCY")
    
    # 开发配置
    SKIP_SSL_VERIFY: bool = Field(default=True, env="SKIP_SSL_VERIFY")
    SKIP_AUTH_IN_DEV: bool = Field(default=False, env="SKIP_AUTH_IN_DEV")
    ENABLE_DEBUG_TOOLBAR: bool = Field(default=True, env="ENABLE_DEBUG_TOOLBAR")
    
    class Config:
        env_file = [".env", "dev.local"]
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取缓存的设置实例"""
    return Settings()


# 全局设置实例
settings = get_settings()
