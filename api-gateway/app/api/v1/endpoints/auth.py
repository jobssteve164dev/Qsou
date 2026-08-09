"""Baseline username/password authentication endpoints."""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class User(BaseModel):
    username: str
    role: str = "admin"


class LoginResponse(BaseModel):
    token: str
    user: User


def _is_auth_enabled() -> bool:
    return bool(settings.QSOU_ADMIN_USERNAME and settings.QSOU_ADMIN_PASSWORD)


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
        username=username,
        role="admin",
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    if not _is_auth_enabled():
        raise HTTPException(status_code=404, detail="Auth disabled in this environment")

    valid = secrets.compare_digest(
        payload.username, settings.QSOU_ADMIN_USERNAME
    ) and secrets.compare_digest(
        payload.password,
        settings.QSOU_ADMIN_PASSWORD,
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return LoginResponse(token=_encode_token(payload.username), user=_user(payload.username))


async def require_current_user(
    authorization: Optional[str] = Header(default=None),
) -> User:
    if not _is_auth_enabled():
        raise HTTPException(status_code=404, detail="Auth disabled in this environment")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return _user(_decode_token(authorization.removeprefix("Bearer ").strip()))


@router.get("/me", response_model=User)
async def me(authorization: Optional[str] = Header(default=None)):
    return await require_current_user(authorization)
