"""
数据处理API端点

接收爬虫数据并进行处理
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

from app.services.data_processing_service import data_processing_service

router = APIRouter()


class DocumentData(BaseModel):
    """文档数据模型"""
    id: str = Field(..., description="文档唯一标识")
    type: str = Field(..., description="文档类型 (news/announcement)")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    url: str = Field(..., description="文档URL")
    source: str = Field(..., description="数据源")
    publish_time: str = Field(..., description="发布时间")
    author: Optional[str] = Field(default="", description="作者")
    tags: Optional[List[str]] = Field(default=[], description="标签")
    category: Optional[str] = Field(default="", description="分类")
    crawl_time: str = Field(..., description="爬取时间")
    content_length: int = Field(..., description="内容长度")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="元数据")


class ProcessRequest(BaseModel):
    """数据处理请求模型"""
    documents: List[DocumentData] = Field(..., description="待处理的文档列表")
    source: str = Field(default="crawler", description="数据来源")
    batch_id: Optional[str] = Field(default=None, description="批次ID")
    enable_elasticsearch: bool = Field(default=True, description="是否启用Elasticsearch索引")
    enable_vector_store: bool = Field(default=True, description="是否启用向量存储")
    enable_nlp_processing: bool = Field(default=True, description="是否启用NLP处理")


class ProcessResponse(BaseModel):
    """数据处理响应模型"""
    status: str = Field(..., description="处理状态")
    message: str = Field(..., description="处理消息")
    processed_count: int = Field(..., description="处理成功的文档数量")
    failed_count: int = Field(..., description="处理失败的文档数量")
    batch_id: str = Field(..., description="批次ID")
    processing_time_ms: int = Field(..., description="处理时间(毫秒)")
    timestamp: str = Field(..., description="处理时间戳")


@router.post("/process", response_model=ProcessResponse)
async def process_documents(
    request: ProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    处理爬虫采集的文档数据
    
    接收爬虫数据，进行清洗、NLP处理、索引和向量化
    """
    start_time = datetime.now()
    
    logger.info(
        "开始处理文档数据",
        document_count=len(request.documents),
        source=request.source,
        batch_id=request.batch_id
    )
    
    try:
        # 转换文档数据格式
        documents = []
        for doc in request.documents:
            doc_dict = doc.dict()
            documents.append(doc_dict)
        
        # 调用数据处理服务
        result = await data_processing_service.process_documents(
            documents=documents,
            source=request.source,
            batch_id=request.batch_id,
            enable_elasticsearch=request.enable_elasticsearch,
            enable_vector_store=request.enable_vector_store,
            enable_nlp_processing=request.enable_nlp_processing
        )
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        response = ProcessResponse(
            status="success",
            message="文档处理完成",
            processed_count=result.get("processed_count", 0),
            failed_count=result.get("failed_count", 0),
            batch_id=result.get("batch_id", request.batch_id or "unknown"),
            processing_time_ms=processing_time,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(
            "文档处理完成",
            processed_count=response.processed_count,
            failed_count=response.failed_count,
            processing_time_ms=processing_time
        )
        
        return response
        
    except Exception as e:
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        logger.error(
            "文档处理失败",
            error=str(e),
            document_count=len(request.documents),
            processing_time_ms=processing_time
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "message": "文档处理失败",
                "error": str(e),
                "processing_time_ms": processing_time
            }
        )


@router.get("/status")
async def get_processing_status():
    """获取数据处理服务状态"""
    try:
        status = await data_processing_service.get_status()
        return status
    except Exception as e:
        logger.error("获取处理状态失败", error=str(e))
        raise HTTPException(status_code=500, detail="获取处理状态失败")


@router.post("/health")
async def health_check():
    """数据处理服务健康检查"""
    try:
        health = await data_processing_service.health_check()
        return health
    except Exception as e:
        logger.error("健康检查失败", error=str(e))
        raise HTTPException(status_code=500, detail="健康检查失败")
