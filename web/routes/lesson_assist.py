"""lesson-assist 파일 관리 라우터 — Daglo 업로드 + 패키지 조회/다운로드."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from ..auth import require_permission
from .. import data_loader

router = APIRouter(prefix="/la")

LA_DATA = Path(os.getenv("LA_DATA_DIR", "/data/lesson-assist"))
DAGLO_DIR = LA_DATA / "input" / "daglo"
PACKAGES_DIR = LA_DATA / "output" / "notebooklm"

MAX_UPLOAD_SIZE = 50 * 1024 * 1024

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAFE_NAME_RE = re.compile(r"^[\w가-힣\s\-_.()]+$")


def _validate_name(name: str, label: str) -> str:
    name = name.strip()
    if not name or not _SAFE_NAME_RE.match(name):
        raise HTTPException(400, f"유효하지 않은 {label}: {name}")
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, f"잘못된 {label}: {name}")
    return name


def _ensure_under(path: Path, base: Path) -> Path:
    """resolved path가 base 아래에 있는지 검증한다."""
    resolved = path.resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise HTTPException(400, "잘못된 경로")
    return resolved


@router.get("/courses")
async def list_course_names(user: dict = Depends(require_permission("sync"))):
    """수강 과목 목록을 반환한다 (school_sync 데이터 기반)."""
    courses = data_loader.courses()
    return {"courses": [c.get("short_name", "") for c in courses if c.get("short_name")]}


def _detect_course(filename: str) -> str | None:
    """파일명에서 과목명을 자동 감지한다 (inbox.py 로직 재사용)."""
    stem = Path(filename).stem
    courses = data_loader.courses()
    known = sorted(
        [c.get("short_name", "") for c in courses if c.get("short_name")],
        key=len, reverse=True,
    )
    for name in known:
        if name in stem:
            return name
    return None


@router.post("/upload")
async def upload_daglo(
    file: UploadFile = File(...),
    course: str = Form(...),
    date: str = Form(None),
    user: dict = Depends(require_permission("sync")),
):
    """Daglo SRT/TXT 파일을 업로드한다."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".srt", ".txt"):
        raise HTTPException(400, "SRT 또는 TXT 파일만 업로드 가능합니다")

    if course == "auto":
        detected = _detect_course(file.filename or "")
        if not detected:
            courses = data_loader.courses()
            names = [c.get("short_name", "") for c in courses if c.get("short_name")]
            return {"status": "needs_course", "filename": file.filename, "courses": names}
        course = detected

    course = _validate_name(course, "과목명")

    known = {c.get("short_name", "") for c in data_loader.courses()}
    if known and course not in known:
        raise HTTPException(400, f"등록되지 않은 과목: {course}")

    if date:
        if not _DATE_RE.match(date):
            raise HTTPException(400, "날짜 형식: YYYY-MM-DD")
        filename = f"{date}{ext}"
    else:
        stem = Path(file.filename or "upload").stem
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", stem)
        if date_match:
            filename = f"{date_match.group()}{ext}"
        else:
            filename = _validate_name(file.filename or "upload.srt", "파일명")

    course_dir = DAGLO_DIR / course
    course_dir.mkdir(parents=True, exist_ok=True)
    dest = _ensure_under(course_dir / filename, DAGLO_DIR)

    content_length = int(file.size or 0) if hasattr(file, 'size') and file.size else 0
    if content_length > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"파일 크기 제한 초과 ({MAX_UPLOAD_SIZE // (1024*1024)}MB)")

    chunks = []
    total = 0
    while True:
        chunk = await file.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE:
            raise HTTPException(413, f"파일 크기 제한 초과 ({MAX_UPLOAD_SIZE // (1024*1024)}MB)")
        chunks.append(chunk)
    content = b"".join(chunks)

    try:
        dest.write_bytes(content)
    except OSError as e:
        raise HTTPException(500, f"파일 저장 실패: {type(e).__name__}")

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
            if not f.is_file() or f.suffix.lower() not in (".srt", ".txt"):
                continue
            try:
                size = f.stat().st_size
            except OSError:
                continue
            date_m = re.search(r"\d{4}-\d{2}-\d{2}", f.stem)
            files.append({
                "filename": f.name,
                "size": size,
                "date": date_m.group() if date_m else None,
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

    path = _ensure_under(DAGLO_DIR / course / filename, DAGLO_DIR)
    if not path.is_file():
        raise HTTPException(404, "파일을 찾을 수 없습니다")

    try:
        path.unlink()
    except OSError as e:
        raise HTTPException(500, f"삭제 실패: {type(e).__name__}")
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

        manifest: dict[str, dict] = {}
        manifest_path = d / ".pack_manifest.json"
        if manifest_path.exists():
            try:
                for entry in json.loads(manifest_path.read_text(encoding="utf-8")):
                    manifest[entry["filename"]] = entry
            except Exception:
                import logging
                logging.getLogger("studyhub.la").warning(f"매니페스트 읽기 실패: {manifest_path}")

        files = []
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            try:
                size = f.stat().st_size
            except OSError:
                continue
            info: dict = {"filename": f.name, "size": size}
            if f.name in manifest:
                info["changed"] = manifest[f.name].get("changed")
            files.append(info)
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

    path = _ensure_under(PACKAGES_DIR / course / filename, PACKAGES_DIR)
    if not path.is_file():
        raise HTTPException(404, "파일을 찾을 수 없습니다")

    encoded = quote(filename, safe="")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}
    return FileResponse(path, headers=headers)
