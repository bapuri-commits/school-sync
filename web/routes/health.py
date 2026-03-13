"""헬스체크 라우터."""

from fastapi import APIRouter

from ..data_loader import last_run

router = APIRouter()


@router.get("/health")
async def health():
    lr = last_run()
    return {
        "status": "ok",
        "service": "study-hub",
        "last_crawl": lr.get("last_run") if lr else None,
    }
