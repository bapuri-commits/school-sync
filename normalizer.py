"""Raw 크롤링 데이터 → 정규화 JSON 변환.

output/raw/ 의 사이트별 JSON을 읽어서
output/normalized/ 에 통합·정규화된 JSON을 생성한다.
"""

import json
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from config import CURRENT_SEMESTER, OUTPUT_DIR
from models import (
    Course, CalendarEvent, Deadline, Assignment,
    Notice, AttendanceRecord, GradeItem, AcademicSchedule,
    StudentProfile, NormalizedOutput,
)

RAW_ECLASS = OUTPUT_DIR / "raw" / "eclass"
RAW_PORTAL = OUTPUT_DIR / "raw" / "portal"
RAW_DEPT = OUTPUT_DIR / "raw" / "department"
RAW_NDRIMS = OUTPUT_DIR / "raw" / "ndrims"
NORM_DIR = OUTPUT_DIR / "normalized"

KST = timezone(timedelta(hours=9))

# 게시판 글 키 매핑 (HTML 테이블 헤더가 일정하지 않음)
_TITLE_KEYS = ("제목", "title", "col_1")
_AUTHOR_KEYS = ("작성자", "author", "col_2")
_DATE_KEYS = ("작성일", "date", "등록일", "col_3")


def _first_match(d: dict, keys: tuple[str, ...], default: str = "") -> str:
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return default


def _unix_to_datetime(ts: int | float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=KST)


def _strip_is_due(name: str) -> str:
    return re.sub(r'\s+is due$', '', name).strip()


def _attendance_status(record: dict) -> str:
    for status in ("출석", "결석", "지각", "조퇴", "유고결석"):
        if record.get(status) == "○":
            return status
    return "미기록"


# ──────────────────────────────────────────────
#  개별 변환 함수
# ──────────────────────────────────────────────

def normalize_courses(raw: dict) -> list[Course]:
    results = []
    for course_data in raw.get("courses", []):
        results.append(Course(
            id=course_data["id"],
            name=course_data["name"],
            short_name=Course.make_short_name(course_data["name"]),
            professor=course_data.get("professor", ""),
            url=course_data.get("url", ""),
        ))
    return results


def normalize_calendar(raw: dict, enrolled_names: set[str] | None = None) -> list[CalendarEvent]:
    results = []
    for evt in raw.get("calendar_events", []):
        start = _unix_to_datetime(evt.get("time_start"))
        if not start:
            continue

        course_name = evt.get("course_name") or None
        if enrolled_names and course_name:
            if not any(course_name in n or n in course_name for n in enrolled_names):
                continue

        duration = evt.get("time_duration", 0) or 0
        end = _unix_to_datetime(evt["time_start"] + duration) if duration > 0 else None

        results.append(CalendarEvent(
            id=evt.get("id"),
            title=_strip_is_due(evt.get("name", "")),
            course_name=course_name,
            start_at=start,
            end_at=end,
            event_type=evt.get("event_type", ""),
            url=evt.get("url", ""),
            source_site="eclass",
        ))
    return results


def normalize_deadlines(raw: dict, calendar: list[CalendarEvent]) -> list[Deadline]:
    """캘린더 이벤트 중 due 타입을 Deadline으로 변환한다."""
    results = []
    for evt in calendar:
        if evt.event_type == "due":
            results.append(Deadline(
                title=evt.title,
                course_name=evt.course_name,
                due_at=evt.start_at,
                source="calendar",
                source_site=evt.source_site,
                url=evt.url,
            ))

    results.sort(key=lambda d: d.due_at)
    return results


def normalize_assignments(raw: dict, courses: list[Course]) -> list[Assignment]:
    """각 과목의 activities에서 과제/활동을 추출한다."""
    results = []
    course_map = {c.id: c for c in courses}

    for course_data in raw.get("courses", []):
        cid = course_data["id"]
        course = course_map.get(cid)
        course_name = course.short_name if course else course_data.get("name", "")

        activities_data = course_data.get("activities", {})
        if isinstance(activities_data, dict) and "_error" not in activities_data:
            for act in activities_data.get("activities", []):
                name = act.get("name", "").replace("\n", " ").strip()
                act_type = act.get("type", "")
                if act_type in ("ubboard", "folder", "ubfile", "resource", "page", "url", "msteams", "vod"):
                    continue
                results.append(Assignment(
                    course_name=course_name,
                    title=name,
                    activity_type=act_type,
                    url=act.get("url", ""),
                    info=act.get("info", ""),
                ))
    return results


def normalize_notices(raw: dict, courses: list[Course]) -> list[Notice]:
    results = []
    course_map = {c.id: c for c in courses}

    for course_data in raw.get("courses", []):
        cid = course_data["id"]
        course = course_map.get(cid)
        course_name = course.short_name if course else course_data.get("name", "")

        boards_data = course_data.get("boards", {})
        if isinstance(boards_data, dict) and "_error" not in boards_data:
            for board_name, board_info in boards_data.items():
                if not isinstance(board_info, dict):
                    continue
                for post in board_info.get("posts", []):
                    title = _first_match(post, _TITLE_KEYS) or "(제목 없음)"
                    results.append(Notice(
                        title=title,
                        board_name=board_name,
                        course_name=course_name,
                        author=_first_match(post, _AUTHOR_KEYS),
                        date=_first_match(post, _DATE_KEYS),
                        url=post.get("_link", ""),
                        category=board_name,
                        source_site="eclass",
                    ))
    return results


def normalize_attendance(raw: dict, courses: list[Course]) -> list[AttendanceRecord]:
    results = []
    course_map = {c.id: c for c in courses}

    for course_data in raw.get("courses", []):
        cid = course_data["id"]
        course = course_map.get(cid)
        course_name = course.short_name if course else course_data.get("name", "")

        att_data = course_data.get("attendance", {})
        if isinstance(att_data, dict) and "_error" not in att_data:
            for rec in att_data.get("records", []):
                week_str = rec.get("주차", "0")
                try:
                    week = int(week_str)
                except ValueError:
                    week = 0

                results.append(AttendanceRecord(
                    course_name=course_name,
                    week=week,
                    date=rec.get("출결 날짜", ""),
                    period=rec.get("교시", ""),
                    status=_attendance_status(rec),
                ))
    return results


def normalize_grades(raw: dict, courses: list[Course]) -> list[GradeItem]:
    results = []
    course_map = {c.id: c for c in courses}

    for course_data in raw.get("courses", []):
        cid = course_data["id"]
        course = course_map.get(cid)
        course_name = course.short_name if course else course_data.get("name", "")

        grades_data = course_data.get("grades", [])
        if isinstance(grades_data, list):
            current_category = ""
            for item in grades_data:
                if isinstance(item, dict) and "_error" not in item:
                    item_name = item.get("성적 항목", "").strip()
                    weight = item.get("가중치", "").strip()

                    if not item_name and weight:
                        current_category = weight
                        continue
                    if not item_name:
                        continue

                    category = "" if item_name == "총점" else current_category

                    results.append(GradeItem(
                        course_name=course_name,
                        category=category,
                        item_name=item_name,
                        score=item.get("성적", "-"),
                        weight=weight,
                        range=item.get("범위", ""),
                        feedback=item.get("피드백", ""),
                    ))
    return results


# ──────────────────────────────────────────────
#  메인 파이프라인
# ──────────────────────────────────────────────

def _load_json(path: Path) -> dict | list | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _normalize_portal_notices(portal_raw: dict) -> list[Notice]:
    """포탈 공지(학사/장학 등)를 Notice 모델로 변환한다."""
    results = []
    for board_code, board_data in portal_raw.items():
        if board_code == "academic_schedule":
            continue
        if not isinstance(board_data, dict) or "_error" in board_data:
            continue
        board_name = board_data.get("board_name", board_code)
        for post in board_data.get("posts", []):
            category = post.get("category", "")
            if not category and board_name == "장학공지":
                category = "장학"
            results.append(Notice(
                title=post.get("title", ""),
                board_name=board_name,
                course_name="",
                author="",
                date=post.get("date", ""),
                url=post.get("url", ""),
                category=category,
                source_site="portal",
            ))
    return results


def _normalize_academic_schedule(portal_raw: dict) -> list[AcademicSchedule]:
    """포탈 학사일정 raw를 AcademicSchedule 모델로 변환한다."""
    results = []
    items = portal_raw.get("academic_schedule", [])
    if not isinstance(items, list):
        return results

    for item in items:
        title_raw = item.get("title", "")
        if not title_raw or len(title_raw) < 5:
            continue

        date_pattern = re.compile(r'(\d{4}\.\d{2}\.\d{2}\.?)')
        dates = date_pattern.findall(title_raw)
        if not dates:
            continue

        start_date = dates[0].rstrip('.').replace('.', '-')
        end_date = dates[1].rstrip('.').replace('.', '-') if len(dates) >= 2 else ""

        title_clean = re.sub(r'\d{4}\.\d{2}\.\d{2}\.?\s*~?\s*', '', title_raw)
        title_clean = title_clean.strip('\t ').replace('바로가기', '').strip()
        if not title_clean:
            continue

        results.append(AcademicSchedule(
            title=title_clean,
            start_date=start_date,
            end_date=end_date,
            department=item.get("department", ""),
            source_site="portal",
        ))
    return results


def _normalize_profile(profile_raw: dict) -> StudentProfile | None:
    """nDRIMS 학적 프로필을 StudentProfile 모델로 변환한다."""
    s = profile_raw.get("student_search", {})
    info = profile_raw.get("student_info", {})
    if not s:
        return None

    campus_code = s.get("CAMPUS_CD", "") or info.get("CAMPUS_CD", "")
    campus_map = {"CM030.10": "서울", "CM030.20": "바이오메디(고양)"}
    campus = campus_map.get(campus_code, campus_code)

    return StudentProfile(
        student_id=str(s.get("STD_NO", "")),
        name=s.get("STD_NM", ""),
        name_en=info.get("STD_ENG_NM", "") or s.get("STD_ENG_NM", ""),
        department=s.get("DPTMJR_NM", ""),
        college=s.get("COLG_NM", ""),
        major=s.get("MJR_NM", ""),
        grade=int(s.get("SCHGRD", 0) or 0),
        enrollment_status=s.get("REGCHG_LCLSF1_CD_NM", ""),
        admission_year=s.get("ENT_YY", ""),
        admission_type=info.get("ENT_DIV_NM", "").split("(")[-1].rstrip(")") if info.get("ENT_DIV_NM") else "",
        total_credits=str(int(float(s.get("ACQ_PNT", 0) or 0))),
        gpa=str(s.get("TT_MRKS_AVG", "")),
        registered_semesters=str(int(s.get("REG_SEM_CNT", 0) or 0)),
        graduation_semesters=int(s.get("CLYY_SEM_CNT", 0) or 0),
        campus=campus,
        email=s.get("EMAIL", ""),
        phone=s.get("HP_NO", ""),
    )


def _normalize_ndrims_grades(grades_raw: dict) -> list[dict]:
    """nDRIMS 전체 성적을 정규화한다. 과목별 + 학기별 요약."""
    result = []
    grade_data = grades_raw.get("grades", {})

    for item in grade_data.get("dsMain", []):
        grade_nm = item.get("RECOD_GRD_NM", "")
        if item.get("RECOD_DEL_NM"):
            grade_nm += f" ({item['RECOD_DEL_NM']})"
        result.append({
            "type": "course",
            "year": item.get("YY", ""),
            "semester": item.get("SEM_NM", ""),
            "course_name": item.get("SBJ_NM", ""),
            "course_name_en": item.get("SBJ_ENG_NM", ""),
            "course_code": item.get("SBJ_NO", ""),
            "category": item.get("CPDIV_NM", ""),
            "credits": float(item.get("CDT", 0) or 0),
            "grade": grade_nm,
            "score": float(item.get("MRK", 0) or 0),
            "professor": item.get("EMP_NM", ""),
            "lecture_lang": item.get("LESN_LANG_NM", ""),
            "curriculum_area": item.get("DETL_CURI_NM", ""),
        })

    for item in grade_data.get("dsSub", []):
        result.append({
            "type": "semester_summary",
            "year": item.get("YY", ""),
            "semester": item.get("SEM_NM", item.get("SEM_CD", "")),
            "applied_credits": int(item.get("APPL_CDT", 0) or 0),
            "earned_credits": int(item.get("GAIN_CDT", 0) or 0),
            "semester_gpa": float(item.get("CERT_AVG_MRK", 0) or 0),
            "cumulative_gpa": float(item.get("MAX_CERT_AVG_MRK", 0) or 0),
            "rank": item.get("RANK", ""),
        })

    return result


def _normalize_ndrims_timetable(tt_raw: dict) -> list[dict]:
    """nDRIMS 개인 시간표를 정규화한다."""
    result = []
    courses = None
    for key in tt_raw:
        data = tt_raw[key]
        if isinstance(data, dict) and "dsMainTkcrs" in data:
            courses = data["dsMainTkcrs"]
            break

    if not courses:
        return result

    for item in courses:
        result.append({
            "course_name": item.get("SBJ_NM", ""),
            "course_code": item.get("SBJ_NO", ""),
            "professor": item.get("EMP_NM", ""),
            "schedule": item.get("TMTBL_KOR_DSC", ""),
            "room": item.get("ROOM_KOR_DSC", ""),
            "credits": item.get("CDT", ""),
            "category": item.get("CPDIV_NM", ""),
            "campus": item.get("LESN_REGN_CD_NM", ""),
        })

    return result


def _normalize_dept_notices(dept_raw: dict) -> list[Notice]:
    """학과 공지를 Notice 모델로 변환한다."""
    results = []
    boards = {
        "notices": ("학과공지", "학과"),
        "external_notices": ("특강/공모전/취업", "특강/공모전"),
    }
    for key, (board_name, category) in boards.items():
        notices = dept_raw.get(key, [])
        if isinstance(notices, list):
            for post in notices:
                results.append(Notice(
                    title=post.get("title", ""),
                    board_name=board_name,
                    course_name="",
                    author=post.get("author", ""),
                    date=post.get("date", ""),
                    url=post.get("url", ""),
                    category=category,
                    source_site="department",
                ))
    return results


def normalize(semester: str = "") -> NormalizedOutput:
    """raw 데이터를 읽어 정규화 JSON을 생성하고 저장한다."""
    semester = semester or CURRENT_SEMESTER

    # --- eclass ---
    eclass_path = RAW_ECLASS / f"{semester}_semester.json"
    if not eclass_path.exists():
        raise FileNotFoundError(f"eclass raw 데이터 없음: {eclass_path}")
    raw = json.loads(eclass_path.read_text(encoding="utf-8"))

    courses = normalize_courses(raw)
    enrolled_full_names = {c["name"] for c in raw.get("courses", [])}
    enrolled_short_names = {c.short_name for c in courses}
    enrolled_names = enrolled_full_names | enrolled_short_names

    calendar = normalize_calendar(raw, enrolled_names=enrolled_names)
    deadlines = normalize_deadlines(raw, calendar)
    assignments = normalize_assignments(raw, courses)
    notices = normalize_notices(raw, courses)
    attendance = normalize_attendance(raw, courses)
    grades = normalize_grades(raw, courses)

    # --- portal ---
    academic_schedule = []
    portal_raw = _load_json(RAW_PORTAL / "portal.json")
    if portal_raw:
        notices.extend(_normalize_portal_notices(portal_raw))
        academic_schedule = _normalize_academic_schedule(portal_raw)

    # --- department ---
    dept_raw = _load_json(RAW_DEPT / "notices.json")
    if dept_raw:
        notices.extend(_normalize_dept_notices(dept_raw))

    # --- ndrims ---
    student_profile = None
    ndrims_grade_history = []
    ndrims_timetable = []
    ndrims_raw = _load_json(RAW_NDRIMS / "ndrims.json")
    if ndrims_raw:
        if "profile" in ndrims_raw:
            student_profile = _normalize_profile(ndrims_raw["profile"])
        if "grades" in ndrims_raw:
            ndrims_grade_history = _normalize_ndrims_grades(ndrims_raw["grades"])
        if "timetable" in ndrims_raw:
            ndrims_timetable = _normalize_ndrims_timetable(ndrims_raw["timetable"])

    output = NormalizedOutput(
        semester=semester,
        normalized_at=datetime.now().isoformat(),
        courses=courses,
        deadlines=deadlines,
        assignments=assignments,
        calendar=calendar,
        notices=notices,
        attendance=attendance,
        grades=grades,
        academic_schedule=academic_schedule,
        student_profile=student_profile,
    )

    _save_normalized(output, ndrims_grade_history, ndrims_timetable)
    _generate_briefing(output)
    _print_summary(output)
    return output


def _save_normalized(output: NormalizedOutput,
                     ndrims_grade_history: list = None,
                     ndrims_timetable: list = None):
    def _write(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, list):
            content = [item.model_dump(mode="json") for item in data]
        else:
            content = data.model_dump(mode="json")
        path.write_text(
            json.dumps(content, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _write_raw(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    ndrims_grade_history = ndrims_grade_history or []
    ndrims_timetable = ndrims_timetable or []

    academics = NORM_DIR / "academics"
    _write(academics / "courses.json", output.courses)
    _write(academics / "deadlines.json", output.deadlines)
    _write(academics / "assignments.json", output.assignments)
    _write(academics / "attendance.json", output.attendance)
    _write(academics / "grades.json", output.grades)

    schedule = NORM_DIR / "schedule"
    _write(schedule / "calendar.json", output.calendar)
    _write(schedule / "academic_schedule.json", output.academic_schedule)

    info = NORM_DIR / "info"
    _write(info / "notices.json", output.notices)

    if output.student_profile:
        profile_dir = NORM_DIR / "profile"
        _write(profile_dir / "student.json", [output.student_profile])

    if ndrims_grade_history:
        _write_raw(NORM_DIR / "profile" / "grade_history.json", ndrims_grade_history)
    if ndrims_timetable:
        _write_raw(NORM_DIR / "schedule" / "timetable.json", ndrims_timetable)

    # 이전 flat 구조 파일 정리
    for old_file in ["courses.json", "deadlines.json", "assignments.json", "attendance.json",
                      "grades.json", "calendar.json", "academic_schedule.json", "notices.json",
                      "student_profile.json"]:
        old_path = NORM_DIR / old_file
        if old_path.exists():
            old_path.unlink()


def _generate_briefing(output: NormalizedOutput):
    """오늘 기준 브리핑 마크다운을 생성한다."""
    today = date.today()
    lines = [f"# school_sync 브리핑 — {today}", ""]

    # 마감 임박
    lines.append("## 마감 임박")
    upcoming = [d for d in output.deadlines if 0 <= d.d_day <= 7]
    if upcoming:
        lines.append("| 과목 | 과제 | D-day | 링크 |")
        lines.append("|------|------|-------|------|")
        for d in upcoming:
            lines.append(f"| {d.course_name or '-'} | {d.title} | D-{d.d_day} | [링크]({d.url}) |")
    else:
        lines.append("임박한 마감 없음")
    lines.append("")

    # 진행 중인 학사일정
    lines.append("## 진행 중인 학사일정")
    today_str = today.isoformat()
    active_schedule = []
    for s in output.academic_schedule:
        if s.end_date:
            if s.start_date <= today_str <= s.end_date:
                active_schedule.append(s)
        elif s.start_date == today_str:
            active_schedule.append(s)
    if active_schedule:
        for s in active_schedule:
            period = f"{s.start_date} ~ {s.end_date}" if s.end_date else s.start_date
            lines.append(f"- {s.title} ({period})")
    else:
        lines.append("오늘 해당하는 학사일정 없음")
    lines.append("")

    # 최근 공지
    lines.append("## 최근 공지 (48시간 이내)")
    recent_notices = [n for n in output.notices if n.date and n.date >= (today - timedelta(days=2)).isoformat()]
    if recent_notices:
        for n in recent_notices[:15]:
            source = {"eclass": "eclass", "portal": "포탈", "department": "학과"}.get(n.source_site, n.source_site)
            prefix = f"[{source}]"
            if n.category:
                prefix = f"[{source}/{n.category}]"
            lines.append(f"- {prefix} {n.title} ({n.date})")
    else:
        lines.append("최근 공지 없음")
    lines.append("")

    # 출석 주의
    lines.append("## 출석 주의")
    absences = [a for a in output.attendance if a.status == "결석"]
    if absences:
        for a in absences:
            lines.append(f"- {a.course_name} {a.week}주차 {a.period} ({a.date}): **결석**")
    else:
        lines.append("결석 기록 없음")
    lines.append("")

    # 프로필 요약
    if output.student_profile:
        p = output.student_profile
        lines.append("## 프로필")
        lines.append(f"- {p.name} | {p.department}")
        lines.append(f"- {p.grade}학년 | 평점 {p.gpa} | 이수 {p.total_credits}학점 / 졸업소요 {p.graduation_semesters}학기")
        lines.append("")

    briefing_path = NORM_DIR / "briefing.md"
    briefing_path.write_text("\n".join(lines), encoding="utf-8")


def _print_summary(output: NormalizedOutput):
    print(f"\n{'='*60}")
    print(f"  정규화 완료 — {output.semester}")
    print(f"{'='*60}")
    print(f"  과목: {len(output.courses)}개")
    print(f"  마감: {len(output.deadlines)}개 (D-day 기준 정렬)")
    if output.deadlines:
        upcoming = [d for d in output.deadlines if d.d_day >= 0]
        if upcoming:
            nearest = upcoming[0]
            print(f"    → 가장 가까운: [{nearest.course_name}] {nearest.title} (D-{nearest.d_day})")
    print(f"  과제/활동: {len(output.assignments)}개")
    print(f"  캘린더: {len(output.calendar)}개")
    print(f"  공지: {len(output.notices)}개")
    print(f"  출석: {len(output.attendance)}개 기록")
    print(f"  성적: {len(output.grades)}개 항목")
    print(f"  학사일정: {len(output.academic_schedule)}개")
    if output.student_profile:
        p = output.student_profile
        print(f"  프로필: {p.name} | {p.major} {p.grade}학년 | 평점 {p.gpa} | {p.total_credits}학점")
    print(f"  출력: {NORM_DIR}/")
    print(f"{'='*60}")
