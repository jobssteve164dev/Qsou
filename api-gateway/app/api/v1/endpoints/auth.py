"""Baseline username/password authentication endpoints."""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
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
    return (
        bool(settings.QSOU_ADMIN_USERNAME and settings.QSOU_ADMIN_PASSWORD)
        or settings.DEBUG
        or settings.SKIP_AUTH_IN_DEV
    )


def _encode_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), encoded, hashlib.sha256
    ).hexdigest()
    return f"{encoded.decode('ascii')}.{signature}"


def _decode_token(token: str) -> str:
    try:
        encoded_text, signature = token.split(".", 1)
        encoded = encoded_text.encode("ascii")
        expected = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), encoded, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        padded = encoded + b"=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if int(payload["exp"]) <= int(time.time()):
            raise ValueError("expired token")
        return str(payload["sub"])
    except (
        binascii.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _user(username: str) -> User:
    return User(
        id="1" if username == "admin" else "2",
        username=username,
        email=f"{username}@example.com",
        role=(
            "admin"
            if username in {"admin", settings.QSOU_ADMIN_USERNAME}
            else "user"
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    if not _is_auth_enabled():
        raise HTTPException(status_code=404, detail="Auth disabled in this environment")

    if settings.QSOU_ADMIN_USERNAME and settings.QSOU_ADMIN_PASSWORD:
        valid = secrets.compare_digest(
            payload.username, settings.QSOU_ADMIN_USERNAME
        ) and secrets.compare_digest(
            payload.password,
            settings.QSOU_ADMIN_PASSWORD,
        )
    else:
        valid = (
            (payload.username == "admin" and payload.password == "admin123")
            or (payload.username == "user" and payload.password == "user123")
        )
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return LoginResponse(token=_encode_token(payload.username), user=_user(payload.username))


@router.get("/me", response_model=User)
async def me(authorization: Optional[str] = Header(default=None)):
    if not _is_auth_enabled():
        raise HTTPException(status_code=404, detail="Auth disabled in this environment")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return _user(_decode_token(authorization.removeprefix("Bearer ").strip()))
