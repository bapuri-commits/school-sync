"""SyOps JWT 인증 + 유저별 권한 시스템.

인증 방식 (우선순위):
1. Authorization: Bearer <token> 헤더
2. syops_token 쿠키 (SyOps 로그인 시 .syworkspace.cloud 도메인으로 설정됨)
3. DEV_MODE=1 환경변수 (개발용 바이패스)

권한 시스템:
- admin role → 전체 권한 (설정 불필요)
- user role → permissions.yaml에 username별 허용 권한 목록
- 미등록 user → 403 차단
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import jwt
import yaml
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

ALGORITHM = "HS256"
SYOPS_TOKEN_COOKIE = "syops_token"

ALL_PERMISSIONS = {"dashboard", "courses", "grades", "materials", "ask", "sync", "notices"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

_PERMISSIONS_PATH = Path(__file__).resolve().parent.parent / "permissions.yaml"


def _get_secret() -> str:
    key = os.getenv("SYOPS_SECRET_KEY", "")
    if not key:
        raise RuntimeError("SYOPS_SECRET_KEY environment variable is not set")
    return key


def _decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def load_permissions() -> dict[str, list[str]]:
    """permissions.yaml를 로드한다. 파일이 없으면 빈 dict 반환."""
    if not _PERMISSIONS_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(_PERMISSIONS_PATH.read_text(encoding="utf-8")) or {}
        return data.get("users", {})
    except Exception:
        return {}


def get_user_permissions(username: str, role: str) -> set[str]:
    """유저의 권한 목록을 반환한다."""
    if role == "admin":
        return ALL_PERMISSIONS.copy()
    perms = load_permissions()
    user_perms = perms.get(username)
    if user_perms is None:
        return set()
    return set(user_perms)


async def require_auth(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    syops_token: str | None = Cookie(None),
) -> dict:
    """JWT 인증. Bearer 헤더 → 쿠키 → DEV_MODE 순으로 시도."""
    if os.getenv("DEV_MODE") == "1":
        return {"sub": "dev", "role": "admin", "username": "dev", "permissions": list(ALL_PERMISSIONS)}

    resolved_token = token or syops_token
    if resolved_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = _decode_token(resolved_token)
    username = payload.get("username", "")
    role = payload.get("role", "user")
    permissions = get_user_permissions(username, role)

    if not permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to StudyHub")

    payload["permissions"] = list(permissions)
    return payload


def require_permission(perm: str):
    """특정 권한이 필요한 엔드포인트에 사용하는 의존성 팩토리."""

    async def _check(user: dict = Depends(require_auth)) -> dict:
        if perm not in user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{perm}' required",
            )
        return user

    return _check
