"""동기화 제어 라우터 — 크롤링/패키징 트리거 + 상태 + 로그."""

from __future__ import annotations

import asyncio
import json
import sys

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import require_permission
from .. import tasks, data_loader

router = APIRouter(prefix="/sync")

PYTHON = sys.executable


class CrawlRequest(BaseModel):
    sites: list[str] = ["eclass"]
    download: bool = False
    course_filter: list[str] | None = None


class PackRequest(BaseModel):
    course: str | None = None
    all_courses: bool = False


@router.get("/status")
async def get_status(user: dict = Depends(require_permission("sync"))):
    state = tasks.get_state()
    return state.to_dict()


@router.get("/last-run")
async def get_last_run(user: dict = Depends(require_permission("sync"))):
    return data_loader.last_run() or {"last_run": None}


@router.get("/logs")
async def get_logs(offset: int = 0, user: dict = Depends(require_permission("sync"))):
    return {"logs": tasks.get_logs(offset), "total": len(tasks.get_state().logs)}


@router.get("/logs/stream")
async def stream_logs(user: dict = Depends(require_permission("sync"))):
    """실행 중인 태스크의 로그를 SSE로 스트리밍한다."""

    async def _generate():
        sent = 0
        while True:
            state = tasks.get_state()
            logs = tasks.get_logs(sent)
            if logs:
                for line in logs:
                    yield f"data: {json.dumps({'type': 'log', 'text': line}, ensure_ascii=False)}\n\n"
                sent += len(logs)

            if state.status != tasks.TaskStatus.RUNNING:
                yield f"data: {json.dumps({'type': 'status', 'status': state.status.value, 'exit_code': state.exit_code})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/crawl")
async def trigger_crawl(body: CrawlRequest, user: dict = Depends(require_permission("sync"))):
    valid_sites = {"eclass", "portal", "department", "ndrims"}
    sites = [s for s in body.sites if s in valid_sites]
    if not sites:
        return {"error": "유효한 사이트가 없습니다", "valid": list(valid_sites)}

    cmd = [PYTHON, "main.py", "--site"] + sites
    if body.download:
        cmd.append("--download")
    if body.course_filter:
        cmd.extend(["--course"] + body.course_filter)

    started = await tasks.run_task("crawl", cmd)
    if not started:
        return {"error": "이미 실행 중인 태스크가 있습니다", "status": tasks.get_state().to_dict()}
    return {"status": "started", "command": cmd}


@router.post("/normalize")
async def trigger_normalize(user: dict = Depends(require_permission("sync"))):
    cmd = [PYTHON, "main.py", "--normalize-only"]
    started = await tasks.run_task("normalize", cmd)
    if not started:
        return {"error": "이미 실행 중인 태스크가 있습니다"}
    return {"status": "started", "command": cmd}


@router.post("/pack")
async def trigger_pack(body: PackRequest, user: dict = Depends(require_permission("sync"))):
    cmd = [PYTHON, "-m", "lesson_assist"]
    if body.all_courses:
        cmd.extend(["pack", "--all", "--no-open", "--no-sync"])
    elif body.course:
        cmd.extend(["pack", "--course", body.course, "--no-open", "--no-sync"])
    else:
        cmd.extend(["run", "--no-open", "--no-sync"])

    la_dir = tasks.PROJECT_ROOT.parent / "lesson-assist"
    started = await tasks.run_task("pack", cmd, cwd=la_dir / "src")
    if not started:
        return {"error": "이미 실행 중인 태스크가 있습니다"}
    return {"status": "started", "command": cmd}
