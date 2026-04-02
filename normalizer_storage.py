"""정규화 데이터 저장 — NormalizedOutput을 파일시스템에 기록한다."""

import json
from pathlib import Path

from config import OUTPUT_DIR
from models import NormalizedOutput

NORM_DIR = OUTPUT_DIR / "normalized"


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, list):
        content = [item.model_dump(mode="json") for item in data]
    else:
        content = data.model_dump(mode="json")
    path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _write_raw(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def save_normalized(output: NormalizedOutput) -> None:
    """NormalizedOutput 전체를 디렉토리 구조에 맞춰 저장한다."""
    academics = NORM_DIR / "academics"
    _write(academics / "courses.json", output.courses)
    _write(academics / "deadlines.json", output.deadlines)
    _write(academics / "assignments.json", output.assignments)
    _write(academics / "attendance.json", output.attendance)
    _write(academics / "grades.json", output.grades)
    if output.syllabus:
        _write(academics / "syllabus.json", output.syllabus)

    schedule = NORM_DIR / "schedule"
    _write(schedule / "calendar.json", output.calendar)
    _write(schedule / "academic_schedule.json", output.academic_schedule)
    if output.timetable:
        _write(schedule / "timetable.json", output.timetable)

    info = NORM_DIR / "info"
    _write(info / "notices.json", output.notices)

    if output.student_profile:
        profile_dir = NORM_DIR / "profile"
        _write(profile_dir / "student.json", [output.student_profile])

    if output.grade_history:
        _write_raw(NORM_DIR / "profile" / "grade_history.json", output.grade_history)

    if output.curriculum_md:
        curriculum_dir = NORM_DIR / "curriculum"
        curriculum_dir.mkdir(parents=True, exist_ok=True)
        (curriculum_dir / "curriculum.md").write_text(output.curriculum_md, encoding="utf-8")

    _cleanup_legacy()


def _cleanup_legacy() -> None:
    """이전 flat 구조 파일을 정리한다."""
    for old_file in [
        "courses.json", "deadlines.json", "assignments.json", "attendance.json",
        "grades.json", "calendar.json", "academic_schedule.json", "notices.json",
        "student_profile.json",
    ]:
        old_path = NORM_DIR / old_file
        if old_path.exists():
            old_path.unlink()
