"""헬스체크 라우터."""

from fastapi import APIRouter, Depends

from ..auth import require_permission
from ..data_loader import last_run

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "study-hub"}


@router.get("/health/detail")
async def health_detail(user: dict = Depends(require_permission("sync"))):
    lr = last_run()
    return {
        "status": "ok",
        "service": "study-hub",
        "last_crawl": lr.get("last_run") if lr else None,
    }
