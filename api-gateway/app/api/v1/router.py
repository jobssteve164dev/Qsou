"""
API v1 主路由
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import auth, data_assets, search
from app.api.v1.endpoints.auth import require_current_user

api_router = APIRouter()

# 注册子路由
api_router.include_router(
    search.router,
    prefix="/search",
    tags=["自有数据搜索"],
    dependencies=[Depends(require_current_user)],
)

api_router.include_router(
    data_assets.router,
    prefix="/data",
    tags=["数据资产"],
    dependencies=[Depends(require_current_user)],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["认证"],
)
