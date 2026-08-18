"""自主数据资产查询、证据查看、导出与回放入口。"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from qsou_data import DataAssetError, DataAssetStore
from app.api.v1.endpoints.auth import User, require_current_user


router = APIRouter()
store = DataAssetStore()


class ReplayRequest(BaseModel):
    source_id: Optional[str] = Field(default=None, description="仅回放指定来源")
    limit: int = Field(default=1000, ge=1, le=10000, description="本次最多回放的文档数")


class SourceSettingsRequest(BaseModel):
    enabled: bool
    schedule: str = Field(description="采集频率：15m、30m、1h、6h、12h 或 24h")
    max_details_per_run: int = Field(ge=1, le=500, description="单次最多处理的详情数")


class SourceAuthorizationRequest(BaseModel):
    decision: str = Field(description="allowed 或 revoked")
    basis: Optional[str] = Field(default=None, description="授权依据类型")
    reference_url: Optional[str] = Field(default=None, description="可核验的授权依据地址")
    scope: Optional[str] = Field(default=None, description="授权覆盖的数据与自动采集范围")
    notes: Optional[str] = Field(default=None, max_length=2000, description="补充说明")
    enable: bool = Field(default=False, description="授权登记后立即开启自动采集")


@router.get("/status")
async def data_asset_status():
    """查看已经掌握的数据规模与处理状态。"""
    return store.status()


@router.get("/sources")
async def list_sources():
    """查看正式登记来源及实际采集状态。"""
    return {"sources": store.list_sources()}


@router.put("/sources/{source_id}/settings")
async def update_source_settings(
    source_id: str,
    request: SourceSettingsRequest,
    current_user: User = Depends(require_current_user),
):
    """更新来源的采集开关、频率和单次上限；权利闸门始终优先。"""
    try:
        return {
            "source": store.update_source_settings(
                source_id,
                enabled=request.enabled,
                schedule=request.schedule,
                max_details_per_run=request.max_details_per_run,
                updated_by=current_user.username,
            )
        }
    except (ValueError, DataAssetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sources/{source_id}/authorization")
async def record_source_authorization(
    source_id: str,
    request: SourceAuthorizationRequest,
    current_user: User = Depends(require_current_user),
):
    """登记或撤销来源的自动采集授权，并返回立即生效的来源状态。"""
    try:
        return {
            "source": store.record_source_authorization(
                source_id,
                decision=request.decision,
                basis=request.basis,
                reference_url=request.reference_url,
                scope=request.scope,
                notes=request.notes,
                enable=request.enable,
                decided_by=current_user.username,
            )
        }
    except (ValueError, DataAssetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/adapter-runs")
async def list_adapter_runs(
    source_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """查看每个来源适配器的真实运行终态和产出指标。"""
    try:
        return {"runs": store.list_adapter_runs(source_id=source_id, limit=limit)}
    except (ValueError, DataAssetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/adapter-runs/{source_id}/trigger", status_code=202)
async def trigger_adapter_run(
    source_id: str,
    current_user: User = Depends(require_current_user),
):
    """把指定来源加入采集队列；重复点击不会制造并行任务。"""
    try:
        return {
            "request": store.request_adapter_run(
                source_id,
                requested_by=current_user.username,
            )
        }
    except (ValueError, DataAssetError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
