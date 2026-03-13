"""대시보드 API — 오늘의 학습 현황 요약."""

from fastapi import APIRouter, Depends

from ..auth import require_permission
from ..data_loader import dashboard_summary

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(require_permission("dashboard"))):
    return dashboard_summary()
