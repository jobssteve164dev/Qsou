"""自主数据资产查询、证据查看、导出与回放入口。"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from qsou_data import DataAssetError, DataAssetStore


router = APIRouter()
store = DataAssetStore()


class ReplayRequest(BaseModel):
    source_id: Optional[str] = Field(default=None, description="仅回放指定来源")
    limit: int = Field(default=1000, ge=1, le=10000, description="本次最多回放的文档数")


@router.get("/status")
async def data_asset_status():
    """查看已经掌握的数据规模与处理状态。"""
    return store.status()


@router.get("/sources")
async def list_sources():
    """查看正式登记来源及实际采集状态。"""
    return {"sources": store.list_sources()}


@router.get("/evidence")
async def list_evidence(
    source_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    try:
        evidence = store.list_evidence(source_id=source_id, limit=limit, offset=offset)
        return {"evidence": evidence, "limit": limit, "offset": offset}
    except (ValueError, DataAssetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evidence/{raw_object_id}")
async def get_evidence(raw_object_id: str):
    try:
        return store.get_evidence(raw_object_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="原始证据不存在") from exc


@router.get("/evidence/{raw_object_id}/content")
async def get_evidence_content(raw_object_id: str):
    try:
        evidence = store.get_evidence(raw_object_id)
        path = store.evidence_body_path(raw_object_id)
        return FileResponse(
            path=str(path),
            media_type=evidence["content_type"].split(";", 1)[0],
            filename=f"{raw_object_id}.body",
            content_disposition_type="inline",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="原始证据不存在") from exc
    except DataAssetError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/documents/{content_version_id}")
async def get_document(content_version_id: str):
    try:
        return store.get_document(content_version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="标准文档不存在") from exc


@router.get("/export")
async def export_documents(source_id: Optional[str] = Query(default=None)):
    """以开放 JSONL 格式导出文档及来源、时间、版本和证据关系。"""
    try:
        if source_id:
            store.registry.get(source_id)
        documents = store.export_documents(source_id=source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def stream():
        for document in documents:
            yield json.dumps(document, ensure_ascii=False, default=str) + "\n"

    filename = f"qsou-{source_id or 'all'}-documents.jsonl"
    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/replay")
async def replay_documents(request: ReplayRequest):
    """把已保存文档重新放入派生处理队列，无需访问外部来源。"""
    try:
        count = store.requeue(source_id=request.source_id, limit=request.limit)
        return {
            "status": "queued",
            "queued_count": count,
            "source_id": request.source_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
