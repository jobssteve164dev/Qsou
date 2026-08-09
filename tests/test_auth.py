import asyncio
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api-gateway"))

from app.api.v1.endpoints import auth


def _configure(monkeypatch):
    monkeypatch.setattr(auth.settings, "DEBUG", False)
    monkeypatch.setattr(auth.settings, "SKIP_AUTH_IN_DEV", False)
    monkeypatch.setattr(auth.settings, "QSOU_ADMIN_USERNAME", "owner")
    monkeypatch.setattr(auth.settings, "QSOU_ADMIN_PASSWORD", "strong-password")
    monkeypatch.setattr(auth.settings, "SECRET_KEY", "test-signing-key")


def test_environment_credentials_issue_a_verifiable_token(monkeypatch):
    _configure(monkeypatch)
    login = asyncio.run(
        auth.login(auth.LoginRequest(username="owner", password="strong-password"))
    )
    current_user = asyncio.run(auth.me(authorization=f"Bearer {login.token}"))
    assert current_user.username == "owner"
    assert current_user.role == "admin"


def test_environment_credentials_reject_wrong_password_and_tampered_token(monkeypatch):
    _configure(monkeypatch)
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(auth.login(auth.LoginRequest(username="owner", password="wrong")))
    assert rejected.value.status_code == 401

    login = asyncio.run(
        auth.login(auth.LoginRequest(username="owner", password="strong-password"))
    )
    with pytest.raises(HTTPException) as rejected_token:
        asyncio.run(auth.me(authorization=f"Bearer {login.token}x"))
    assert rejected_token.value.status_code == 401
