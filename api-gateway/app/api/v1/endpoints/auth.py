"""
开发环境最小可用的认证端点
提供 /auth/login 与 /auth/me，便于前端静默登录联调
仅在 DEBUG 或 SKIP_AUTH_IN_DEV 开启时可用
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.config import settings


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: str
    username: str
    email: str
    role: str = "admin"
    created_at: str


class LoginResponse(BaseModel):
    token: str
    user: User


def _is_auth_enabled() -> bool:
    # 在开发阶段默认启用；可通过环境变量关闭
    return settings.DEBUG or settings.SKIP_AUTH_IN_DEV


def _fake_token(username: str) -> str:
    exp = (datetime.utcnow() + timedelta(hours=8)).isoformat()
    return f"dev-{username}-{exp}"


def _fake_user(username: str) -> User:
    return User(
        id="1" if username == "admin" else "2",
        username=username,
        email=f"{username}@example.com",
        role="admin" if username == "admin" else "user",
        created_at=datetime.utcnow().isoformat(),
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    if not _is_auth_enabled():
        raise HTTPException(status_code=404, detail="Auth disabled in this environment")

    # 最小校验：接受演示账号 admin/admin123 与 user/user123
    valid = (
        (payload.username == "admin" and payload.password == "admin123")
        or (payload.username == "user" and payload.password == "user123")
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return LoginResponse(token=_fake_token(payload.username), user=_fake_user(payload.username))


@router.get("/me", response_model=User)
async def me(token: Optional[str] = None):
    if not _is_auth_enabled():
        raise HTTPException(status_code=404, detail="Auth disabled in this environment")

    # 前端通过 Authorization: Bearer <token> 发送；为简化，这里直接返回 admin
    return _fake_user("admin")


