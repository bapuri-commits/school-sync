"""normalized JSON 데이터 로더.

school_sync가 생성한 output/normalized/ 디렉토리의 JSON/MD 파일을
읽어서 API 응답용 데이터를 제공한다.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_OUTPUT_DIR: Path | None = None


def init(output_dir: Path) -> None:
    global _OUTPUT_DIR
    _OUTPUT_DIR = output_dir / "normalized"


def _base() -> Path:
    if _OUTPUT_DIR is None:
        raise RuntimeError("data_loader not initialized — call init() first")
    return _OUTPUT_DIR


def _read_json(rel_path: str) -> Any:
    path = _base() / rel_path
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _read_text(rel_path: str) -> str:
    path = _base() / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def courses() -> list[dict]:
    return _read_json("academics/courses.json")


def deadlines() -> list[dict]:
    return _read_json("academics/deadlines.json")


def assignments() -> list[dict]:
    return _read_json("academics/assignments.json")


def attendance() -> list[dict]:
    return _read_json("academics/attendance.json")


def grades() -> list[dict]:
    return _read_json("academics/grades.json")


def syllabus() -> list[dict]:
    return _read_json("academics/syllabus.json")


def notices() -> list[dict]:
    return _read_json("info/notices.json")


def timetable() -> list[dict]:
    return _read_json("schedule/timetable.json")


def calendar_events() -> list[dict]:
    return _read_json("schedule/calendar.json")


def academic_schedule() -> list[dict]:
    return _read_json("schedule/academic_schedule.json")


def briefing() -> str:
    return _read_text("briefing.md")


def last_run() -> dict | None:
    path = _base().parent / ".last_run.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def downloads_manifest(course_name: str) -> list[dict]:
    """과목별 다운로드 매니페스트를 로드한다."""
    downloads_dir = _base().parent / "downloads"
    if not downloads_dir.exists():
        return []
    for d in downloads_dir.iterdir():
        if d.is_dir() and course_name in d.name:
            manifest = d / "manifest.json"
            if manifest.exists():
                try:
                    return json.loads(manifest.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    return []
    return []


def context_markdown(course_name: str) -> str:
    """과목별 학습 컨텍스트 마크다운을 로드한다."""
    ctx_dir = _base().parent / "context"
    if not ctx_dir.exists():
        return ""
    for f in ctx_dir.iterdir():
        if f.suffix == ".md" and course_name in f.stem:
            return f.read_text(encoding="utf-8")
    return ""


def _filter_by_course(data: list[dict], course_name: str, key: str = "course_name") -> list[dict]:
    return [d for d in data if d.get(key, "") == course_name]


def course_detail(course_name: str) -> dict:
    """과목 하나에 대한 통합 상세 정보를 반환한다."""
    all_syl = syllabus()
    syl = next((s for s in all_syl if s.get("course_name") == course_name), None)

    return {
        "syllabus": syl,
        "grades": _filter_by_course(grades(), course_name),
        "attendance": _filter_by_course(attendance(), course_name),
        "notices": _filter_by_course(notices(), course_name),
        "assignments": _filter_by_course(assignments(), course_name),
        "deadlines": _filter_by_course(deadlines(), course_name),
        "materials": downloads_manifest(course_name),
    }


def dashboard_summary() -> dict:
    """대시보드용 요약 데이터를 반환한다."""
    today_str = date.today().isoformat()
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][date.today().weekday()]

    tt = timetable()
    today_classes = [t for t in tt if weekday_kr in t.get("schedule", "")]

    dl = deadlines()
    upcoming = [d for d in dl if d.get("d_day") is not None and -1 <= d["d_day"] <= 7]
    upcoming.sort(key=lambda d: d.get("d_day", 999))

    all_notices = notices()
    notice_cutoff = (date.today() - timedelta(days=30)).isoformat()
    eclass_notices = sorted(
        [n for n in all_notices if n.get("source_site") == "eclass" and n.get("date", "") >= notice_cutoff],
        key=lambda n: n.get("date", ""), reverse=True,
    )
    other_notices = sorted(
        [n for n in all_notices if n.get("source_site") != "eclass" and n.get("date", "") >= notice_cutoff],
        key=lambda n: n.get("date", ""), reverse=True,
    )

    cutoff = (date.today() - timedelta(days=2)).isoformat()
    new_notice_courses = set()
    for n in eclass_notices:
        if n.get("date", "") >= cutoff and n.get("course_name"):
            new_notice_courses.add(n.get("course_name", ""))

    return {
        "today": today_str,
        "weekday": weekday_kr,
        "today_classes": today_classes,
        "upcoming_deadlines": upcoming,
        "recent_eclass_notices": eclass_notices[:8],
        "recent_other_notices": other_notices[:8],
        "new_notice_courses": sorted(new_notice_courses),
        "last_run": last_run(),
    }
