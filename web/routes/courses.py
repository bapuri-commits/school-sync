"""과목 관련 API — 목록, 상세, 세부 데이터, 자료 다운로드."""

import os
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..auth import require_permission
from .. import data_loader

router = APIRouter(prefix="/courses")

_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", Path(__file__).resolve().parent.parent.parent / "output"))
_DOWNLOADS_DIR = _OUTPUT_DIR / "downloads"
_SAFE_NAME_RE = re.compile(r"^[\w가-힣\s\-_.()]+$")


@router.get("")
async def list_courses(user: dict = Depends(require_permission("courses"))):
    return data_loader.courses()


@router.get("/{name}")
async def get_course(name: str, user: dict = Depends(require_permission("courses"))):
    all_courses = data_loader.courses()
    course = next((c for c in all_courses if c.get("short_name") == name), None)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{name}' not found")

    detail = data_loader.course_detail(name)

    perms = set(user.get("permissions", []))
    if "grades" not in perms:
        detail["grades"] = []
        detail["attendance"] = []

    return {**course, **detail}


@router.get("/{name}/syllabus")
async def get_syllabus(name: str, user: dict = Depends(require_permission("courses"))):
    all_syl = data_loader.syllabus()
    syl = next((s for s in all_syl if s.get("course_name") == name), None)
    if not syl:
        raise HTTPException(status_code=404, detail="Syllabus not found")
    return syl


@router.get("/{name}/context")
async def get_context(name: str, user: dict = Depends(require_permission("courses"))):
    md = data_loader.context_markdown(name)
    if not md:
        raise HTTPException(status_code=404, detail="Context not found")
    return {"course": name, "markdown": md}


def _find_course_dir(course_name: str) -> Path | None:
    """과목명과 정확히 일치하는 downloads 하위 디렉토리를 찾는다."""
    if not _DOWNLOADS_DIR.exists():
        return None
    exact = _DOWNLOADS_DIR / course_name
    if exact.is_dir():
        return exact
    for d in _DOWNLOADS_DIR.iterdir():
        if d.is_dir() and d.name == course_name:
            return d
    return None


@router.get("/{name}/download/{filename}")
async def download_material(
    name: str,
    filename: str,
    user: dict = Depends(require_permission("materials")),
):
    """과목의 다운로드된 수업자료 파일을 서빙한다."""
    if not _SAFE_NAME_RE.match(filename) or ".." in filename:
        raise HTTPException(400, "유효하지 않은 파일명")

    course_dir = _find_course_dir(name)
    if not course_dir:
        raise HTTPException(404, f"과목 자료 폴더 없음: {name}")

    file_path = (course_dir / filename).resolve()
    if not file_path.is_relative_to(course_dir.resolve()):
        raise HTTPException(400, "잘못된 경로")
    if not file_path.is_file():
        raise HTTPException(404, f"파일 없음: {filename}")

    encoded = quote(filename, safe="")
    return FileResponse(
        file_path,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
