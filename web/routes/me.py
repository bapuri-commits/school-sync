"""유저 정보 + 권한 조회 API."""

from fastapi import APIRouter, Depends

from ..auth import require_auth

router = APIRouter()


@router.get("/me")
async def get_me(user: dict = Depends(require_auth)):
    return {
        "username": user.get("username", ""),
        "role": user.get("role", "user"),
        "permissions": user.get("permissions", []),
    }
