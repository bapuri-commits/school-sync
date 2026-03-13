"""전체 데이터 조회 API — 시간표, 마감, 공지, 출석, 성적."""

from fastapi import APIRouter, Depends

from ..auth import require_permission
from .. import data_loader

router = APIRouter()


@router.get("/timetable")
async def get_timetable(user: dict = Depends(require_permission("dashboard"))):
    return data_loader.timetable()


@router.get("/deadlines")
async def get_deadlines(user: dict = Depends(require_permission("dashboard"))):
    return data_loader.deadlines()


@router.get("/notices")
async def get_notices(user: dict = Depends(require_permission("notices"))):
    return data_loader.notices()


@router.get("/attendance")
async def get_attendance(user: dict = Depends(require_permission("grades"))):
    return data_loader.attendance()


@router.get("/grades")
async def get_grades(user: dict = Depends(require_permission("grades"))):
    return data_loader.grades()


@router.get("/briefing")
async def get_briefing(user: dict = Depends(require_permission("dashboard"))):
    return {"markdown": data_loader.briefing()}


@router.get("/calendar")
async def get_calendar(user: dict = Depends(require_permission("dashboard"))):
    return data_loader.calendar_events()
