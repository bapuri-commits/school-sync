"""lesson-assist 파일 관리 라우터 — Daglo 업로드 + 패키지 조회/다운로드."""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from ..auth import require_permission

router = APIRouter(prefix="/la")

LA_DATA = Path(os.getenv("LA_DATA_DIR", "/data/lesson-assist"))
DAGLO_DIR = LA_DATA / "input" / "daglo"
PACKAGES_DIR = LA_DATA / "output" / "notebooklm"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_NAME_RE = re.compile(r"^[\w가-힣\s\-_.()]+$")


def _validate_name(name: str, label: str) -> str:
    name = name.strip()
    if not name or not _SAFE_NAME_RE.match(name):
        raise HTTPException(400, f"유효하지 않은 {label}: {name}")
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, f"잘못된 {label}: {name}")
    return name


@router.post("/upload")
async def upload_daglo(
    file: UploadFile = File(...),
    course: str = Form(...),
    date: str = Form(None),
    user: dict = Depends(require_permission("sync")),
):
    """Daglo SRT/TXT 파일을 업로드한다."""
    course = _validate_name(course, "과목명")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".srt", ".txt"):
        raise HTTPException(400, "SRT 또는 TXT 파일만 업로드 가능합니다")

    if date:
        if not _DATE_RE.match(date):
            raise HTTPException(400, "날짜 형식: YYYY-MM-DD")
        filename = f"{date}{ext}"
    else:
        stem = Path(file.filename).stem
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", stem)
        if date_match:
            filename = f"{date_match.group()}{ext}"
        else:
            filename = file.filename or "upload.srt"

    course_dir = DAGLO_DIR / course
    course_dir.mkdir(parents=True, exist_ok=True)
    dest = course_dir / filename

    content = await file.read()
    dest.write_bytes(content)

    return {
        "status": "uploaded",
        "course": course,
        "filename": filename,
        "size": len(content),
        "path": f"{course}/{filename}",
    }


@router.get("/files")
async def list_files(user: dict = Depends(require_permission("sync"))):
    """업로드된 Daglo 파일을 과목별로 반환한다."""
    if not DAGLO_DIR.exists():
        return {"courses": []}

    courses = []
    for d in sorted(DAGLO_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "inbox":
            continue
        files = []
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix.lower() in (".srt", ".txt"):
                files.append({
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "date": re.search(r"\d{4}-\d{2}-\d{2}", f.stem).group() if re.search(r"\d{4}-\d{2}-\d{2}", f.stem) else None,
                })
        if files:
            courses.append({"course": d.name, "files": files})

    return {"courses": courses}


@router.delete("/files/{course}/{filename}")
async def delete_file(
    course: str,
    filename: str,
    user: dict = Depends(require_permission("sync")),
):
    """Daglo 파일을 삭제한다."""
    course = _validate_name(course, "과목명")
    filename = _validate_name(filename, "파일명")

    path = (DAGLO_DIR / course / filename).resolve()
    if not str(path).startswith(str(DAGLO_DIR.resolve())):
        raise HTTPException(400, "잘못된 경로")
    if not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다")

    path.unlink()
    return {"status": "deleted", "path": f"{course}/{filename}"}


@router.get("/packages")
async def list_packages(user: dict = Depends(require_permission("sync"))):
    """생성된 NotebookLM 패키지를 과목별로 반환한다."""
    if not PACKAGES_DIR.exists():
        return {"packages": []}

    packages = []
    for d in sorted(PACKAGES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        files = []
        for f in sorted(d.iterdir()):
            if f.is_file():
                files.append({
                    "filename": f.name,
                    "size": f.stat().st_size,
                })
        if files:
            packages.append({"course": d.name, "files": files})

    return {"packages": packages}


@router.get("/packages/{course}/{filename}")
async def download_package_file(
    course: str,
    filename: str,
    user: dict = Depends(require_permission("sync")),
):
    """패키지 파일을 다운로드한다."""
    course = _validate_name(course, "과목명")
    filename = _validate_name(filename, "파일명")

    path = (PACKAGES_DIR / course / filename).resolve()
    if not str(path).startswith(str(PACKAGES_DIR.resolve())):
        raise HTTPException(400, "잘못된 경로")
    if not path.exists():
        raise HTTPException(404, "파일을 찾을 수 없습니다")

    return FileResponse(path, filename=filename)
