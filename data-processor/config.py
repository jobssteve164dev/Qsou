"""
数据处理模块配置
"""
import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class ProcessorConfig(BaseSettings):
    """数据处理器配置"""
    
    # 基础配置
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # 数据库配置
    elasticsearch_url: str = Field(default="http://localhost:9200", env="ELASTICSEARCH_URL")
    qdrant_url: str = Field(default="http://localhost:6333", env="QDRANT_URL")
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    postgres_url: str = Field(default="postgresql://user:pass@localhost:5432/qsou", env="POSTGRES_URL")
    
    # NLP模型配置
    chinese_model_name: str = Field(default="bert-base-chinese", env="CHINESE_MODEL_NAME")
    financial_model_name: str = Field(default="ProsusAI/finbert", env="FINANCIAL_MODEL_NAME")
    embedding_model_name: str = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", env="EMBEDDING_MODEL_NAME")
    
    # 处理参数
    batch_size: int = Field(default=32, env="BATCH_SIZE")
    max_text_length: int = Field(default=512, env="MAX_TEXT_LENGTH")
    min_text_length: int = Field(default=10, env="MIN_TEXT_LENGTH")
    similarity_threshold: float = Field(default=0.85, env="SIMILARITY_THRESHOLD")
    
    # 数据质量参数
    min_word_count: int = Field(default=20, env="MIN_WORD_COUNT")
    max_word_count: int = Field(default=10000, env="MAX_WORD_COUNT")
    quality_score_threshold: float = Field(default=0.6, env="QUALITY_SCORE_THRESHOLD")
    
    # 向量化配置
    vector_dimension: int = Field(default=384, env="VECTOR_DIMENSION")
    qdrant_collection_name: str = Field(default="investment_documents", env="QDRANT_COLLECTION_NAME")
    
    # Elasticsearch配置
    es_index_prefix: str = Field(default="qsou", env="ES_INDEX_PREFIX")
    es_news_index: str = Field(default="qsou_news", env="ES_NEWS_INDEX")
    es_announcements_index: str = Field(default="qsou_announcements", env="ES_ANNOUNCEMENTS_INDEX")
    
    # 任务队列配置
    celery_broker_url: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局配置实例
config = ProcessorConfig()
