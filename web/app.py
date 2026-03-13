"""StudyHub — school_sync + lesson-assist 통합 웹 서비스.

실행:
    # 개발 모드 (인증 없이)
    DEV_MODE=1 uvicorn web.app:app --reload --port 8000

    # 프로덕션
    uvicorn web.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import data_loader
from .routes import health, dashboard, courses, data, ask, sync, me, lesson_assist

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", Path(__file__).resolve().parent.parent / "output"))
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_loader.init(OUTPUT_DIR)
    from .auto_sync import auto_sync_loop
    sync_task = asyncio.create_task(auto_sync_loop())
    yield
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="StudyHub",
    description="school_sync + lesson-assist 통합 학습 도우미",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://study.syworkspace.cloud"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(lesson_assist.router, prefix="/api")

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """SPA fallback — API 이외의 모든 경로에 index.html 서빙."""
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        file_path = (FRONTEND_DIR / full_path).resolve()
        if not str(file_path).startswith(str(FRONTEND_DIR.resolve())):
            return FileResponse(FRONTEND_DIR / "index.html")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
