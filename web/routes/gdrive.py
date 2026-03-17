"""Google Drive 연동 라우터 — 수동 업로드 + 자동 전송."""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_permission
from ..gdrive import GDRIVE_ENABLED, GDRIVE_ROOT_FOLDER_ID, get_uploader

_SAFE_NAME_RE = re.compile(r"^[\w가-힣\s\-_.()]+$")


def _validate_course(name: str) -> str:
    name = name.strip()
    if not name or not _SAFE_NAME_RE.match(name) or ".." in name:
        raise HTTPException(400, f"유효하지 않은 과목명: {name}")
    return name

router = APIRouter(prefix="/gdrive")

LA_DATA = Path(os.getenv("LA_DATA_DIR", "/data/lesson-assist"))
PACKAGES_DIR = LA_DATA / "output" / "notebooklm"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
DOWNLOADS_DIR = OUTPUT_DIR / "downloads"


@router.get("/status")
async def gdrive_status(user: dict = Depends(require_permission("sync"))):
    return {"enabled": GDRIVE_ENABLED}


class UploadPackageRequest(BaseModel):
    course: str


@router.post("/upload/package")
async def upload_package_to_drive(
    body: UploadPackageRequest,
    user: dict = Depends(require_permission("sync")),
):
    """특정 과목의 NotebookLM 패키지를 Google Drive로 업로드."""
    if not GDRIVE_ENABLED:
        raise HTTPException(503, "Google Drive가 설정되지 않았습니다")

    course = _validate_course(body.course)
    course_dir = PACKAGES_DIR / course
    if not course_dir.is_dir():
        raise HTTPException(404, f"패키지를 찾을 수 없습니다: {course}")

    uploader = get_uploader()
    studyhub_folder = uploader.find_or_create_folder("StudyHub", GDRIVE_ROOT_FOLDER_ID)
    packages_folder = uploader.find_or_create_folder("수업자료", studyhub_folder)
    course_folder = uploader.find_or_create_folder(course, packages_folder)

    results = uploader.upload_directory(str(course_dir), course_folder)

    uploaded = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    return {
        "ok": True,
        "course": body.course,
        "uploaded": len(uploaded),
        "failed": len(failed),
        "files": results,
    }


class UploadDownloadsRequest(BaseModel):
    course: str


@router.post("/upload/downloads")
async def upload_downloads_to_drive(
    body: UploadDownloadsRequest,
    user: dict = Depends(require_permission("sync")),
):
    """크롤링 다운로드 파일을 Google Drive로 업로드."""
    if not GDRIVE_ENABLED:
        raise HTTPException(503, "Google Drive가 설정되지 않았습니다")

    course = _validate_course(body.course)
    course_dir = DOWNLOADS_DIR / course
    if not course_dir.is_dir():
        raise HTTPException(404, f"다운로드 폴더를 찾을 수 없습니다: {course}")

    uploader = get_uploader()
    studyhub_folder = uploader.find_or_create_folder("StudyHub", GDRIVE_ROOT_FOLDER_ID)
    dl_folder = uploader.find_or_create_folder("크롤링", studyhub_folder)
    course_folder = uploader.find_or_create_folder(course, dl_folder)

    results = uploader.upload_directory(str(course_dir), course_folder)

    uploaded = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    return {
        "ok": True,
        "course": body.course,
        "uploaded": len(uploaded),
        "failed": len(failed),
        "files": results,
    }
