"""과목별 학습 컨텍스트를 생성하여 output/context/에 저장한다.

lesson-assist 등 외부 소비자를 위한 가공 레이어.
정규화 데이터에서 학습에 필요한 정보만 추출하여 과목별 마크다운으로 통합한다.

포함: 강의계획서, 과제/마감, 공지사항 (학습 관련)
제외: 성적, 출석, 학교 행사 (학사 관리는 ask.py 영역)
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from config import OUTPUT_DIR

NORM_DIR = OUTPUT_DIR / "normalized"
CONTEXT_DIR = OUTPUT_DIR / "context"


def export_all() -> int:
    """모든 수강 과목의 학습 컨텍스트를 생성한다.

    Returns:
        생성된 컨텍스트 파일 수.
    """
    courses = _load_json(NORM_DIR / "academics" / "courses.json")
    if not courses:
        print("[context_export] courses.json이 없습니다. 정규화를 먼저 실행하세요.")
        return 0

    course_names = sorted({c["short_name"] for c in courses if c.get("short_name")})
    if not course_names:
        print("[context_export] 수강 과목이 없습니다.")
        return 0

    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─'*40}")
    print("  학습 컨텍스트 생성")
    print(f"{'─'*40}")

    generated = 0
    for name in course_names:
        content = build_context(name)
        if content:
            path = CONTEXT_DIR / f"{name}.md"
            path.write_text(content, encoding="utf-8")
            generated += 1
            print(f"  ✓ {name}")
        else:
            print(f"  - {name} (데이터 없음, 건너뜀)")

    print(f"  → {generated}/{len(course_names)}개 과목 → {CONTEXT_DIR}/")
    return generated


def build_context(course: str) -> str:
    """특정 과목의 학습 컨텍스트 마크다운을 생성한다."""
    if not NORM_DIR.exists():
        return ""

    sections: list[str] = []

    syllabus_md = _build_syllabus_section(course)
    if syllabus_md:
        sections.append(syllabus_md)

    assignments_md = _build_assignments_section(course)
    if assignments_md:
        sections.append(assignments_md)

    notices_md = _build_notices_section(course)
    if notices_md:
        sections.append(notices_md)

    if not sections:
        return ""

    frontmatter = _build_frontmatter(course)
    header = f"# {course} 학습 컨텍스트\n\n> school_sync에서 자동 생성됨\n"
    body = "\n---\n\n".join(sections)

    return f"{frontmatter}\n\n{header}\n{body}\n"


def get_week_topic(course: str, target_date: str) -> tuple[int, str] | None:
    """강의계획서에서 날짜에 해당하는 주차와 토픽을 조회한다.

    Returns:
        (week_number, topic) 또는 None
    """
    syllabus = _find_course_syllabus(course)
    if not syllabus:
        return None

    weekly_plan = syllabus.get("weekly_plan", [])
    if not weekly_plan:
        return None

    semester_start = _estimate_semester_start()
    if semester_start:
        try:
            target = date.fromisoformat(target_date)
            week_num = max(1, (target - semester_start).days // 7 + 1)
            for wp in weekly_plan:
                if wp["week"] == week_num:
                    return (week_num, wp["topic"])
        except ValueError:
            pass

    return (weekly_plan[-1]["week"], weekly_plan[-1]["topic"])


# ──────────────────────────────────────────────
#  내부 헬퍼
# ──────────────────────────────────────────────

def _load_json(path: Path) -> list | dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_course_syllabus(course: str) -> dict | None:
    data = _load_json(NORM_DIR / "academics" / "syllabus.json")
    if not data or not isinstance(data, list):
        return None

    exact = [s for s in data if s.get("course_name") == course]
    if exact:
        return exact[0]

    partial = [s for s in data if course in s.get("course_name", "")]
    return partial[0] if partial else None


def _estimate_semester_start() -> date | None:
    """학사일정에서 학기 시작일을 추정한다."""
    schedule = _load_json(NORM_DIR / "schedule" / "academic_schedule.json")
    if not schedule or not isinstance(schedule, list):
        return None

    for item in schedule:
        title = item.get("title", "")
        if re.search(r"수업\s*시작|개강|학기\s*시작", title):
            start = item.get("start_date", "")
            if start:
                try:
                    return date.fromisoformat(start)
                except ValueError:
                    pass
    return None


def _build_frontmatter(course: str) -> str:
    lines = [
        "---",
        f'course: "{course}"',
        f'generated_at: "{datetime.now().isoformat(timespec="seconds")}"',
    ]

    week_info = get_week_topic(course, date.today().isoformat())
    if week_info:
        week_num, topic = week_info
        lines.append(f"current_week: {week_num}")
        lines.append(f'current_topic: "{topic}"')

    lines.append("---")
    return "\n".join(lines)


def _build_syllabus_section(course: str) -> str:
    entry = _find_course_syllabus(course)
    if not entry:
        return ""

    lines = ["## 강의계획서\n"]

    meta_fields = [
        ("담당교수", "professor"),
        ("이메일", "email"),
        ("강의실/시간", "classroom"),
        ("이수구분", "category"),
        ("수업방식", "class_type"),
        ("상담시간", "office_hours"),
    ]
    for label, key in meta_fields:
        val = entry.get(key, "")
        if val and val.strip():
            lines.append(f"- **{label}**: {val}")

    if any(entry.get(key) for _, key in meta_fields):
        lines.append("")

    if entry.get("overview"):
        lines.append(f"### 강의개요\n\n{entry['overview']}\n")
    if entry.get("objectives"):
        lines.append(f"### 강의목표\n\n{entry['objectives']}\n")

    textbooks = entry.get("textbooks", [])
    if textbooks:
        lines.append("### 교재\n")
        for tb in textbooks:
            lines.append(f"- [{tb.get('type', '교재')}] {tb.get('title', '')}")
        lines.append("")

    weekly_plan = entry.get("weekly_plan", [])
    if weekly_plan:
        lines.append("### 주차별 계획\n")
        lines.append("| 주차 | 토픽 |")
        lines.append("|------|------|")
        for wp in weekly_plan:
            lines.append(f"| {wp['week']}주차 | {wp['topic']} |")
        lines.append("")

    return "\n".join(lines) if len(lines) > 1 else ""


def _build_assignments_section(course: str) -> str:
    parts: list[str] = []

    assignments = _load_json(NORM_DIR / "academics" / "assignments.json")
    if assignments and isinstance(assignments, list):
        matched = [a for a in assignments if course in a.get("course_name", "")]
        if matched:
            lines = ["## 과제/활동\n"]
            for a in matched:
                deadline = a.get("deadline", "")
                suffix = f" (마감: {deadline})" if deadline else ""
                lines.append(f"- **{a.get('title', '?')}**{suffix}")
                if a.get("info"):
                    lines.append(f"  - {a['info']}")
            parts.append("\n".join(lines))

    deadlines = _load_json(NORM_DIR / "academics" / "deadlines.json")
    if deadlines and isinstance(deadlines, list):
        matched = [d for d in deadlines if course in d.get("course_name", "")]
        if matched:
            lines = ["## 마감 일정\n"]
            for d in matched:
                lines.append(
                    f"- {d.get('due_at', '?')} | {d.get('title', '?')} ({d.get('source', '')})"
                )
            parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _build_notices_section(course: str) -> str:
    data = _load_json(NORM_DIR / "info" / "notices.json")
    if not data or not isinstance(data, list):
        return ""

    cutoff = (date.today() - timedelta(days=14)).isoformat()
    matched = [
        n for n in data
        if course in n.get("course_name", "")
        and n.get("date", "") >= cutoff
    ]

    if not matched:
        return ""

    lines = ["## 최근 공지사항\n"]
    for n in matched[:10]:
        lines.append(f"- [{n.get('date', '')}] **{n.get('title', '?')}**")
        if n.get("board_name"):
            lines.append(f"  - 게시판: {n['board_name']}")

    return "\n".join(lines)
