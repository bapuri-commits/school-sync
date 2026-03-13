"""과목 관련 API — 목록, 상세, 세부 데이터."""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_permission
from .. import data_loader

router = APIRouter(prefix="/courses")


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
