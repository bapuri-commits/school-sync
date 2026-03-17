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
    StudentProfile, NormalizedOutput, TimetableEntry,
    SyllabusEntry, SyllabusTextbook, SyllabusWeek,
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


def _normalize_date(raw_date: str) -> str:
    """다양한 날짜 형식을 YYYY-MM-DD ISO로 통일한다."""
    if not raw_date:
        return ""
    d = raw_date.strip()
    d = re.sub(r'[./]', '-', d)
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', d)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m = re.match(r'^(\d{2})-(\d{1,2})-(\d{1,2})', d)
    if m:
        return f"20{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return raw_date.strip()


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


_SKIP_ACTIVITY_TYPES = {"ubboard", "folder", "ubfile", "resource", "page", "url", "msteams", "vod"}


def normalize_assignments(raw: dict, courses: list[Course]) -> list[Assignment]:
    """각 과목의 activities에서 과제/활동을 추출한다."""
    results = []
    course_map = {c.id: c for c in courses}

    for course_data in raw.get("courses", []):
        cid = course_data["id"]
        course = course_map.get(cid)
        course_name = course.short_name if course else course_data.get("name", "")

        activities_data = course_data.get("activities", {})
        if not isinstance(activities_data, dict) or "_error" in activities_data:
            continue

        seen_urls = set()
        all_activities = list(activities_data.get("activities", []))
        for section in activities_data.get("sections", []):
            for act in section.get("activities", []):
                if act.get("url") and act["url"] not in seen_urls:
                    all_activities.append(act)

        for act in all_activities:
            name = act.get("name", "").replace("\n", " ").strip()
            act_type = act.get("type", "")
            act_url = act.get("url", "")
            if act_type in _SKIP_ACTIVITY_TYPES:
                continue
            if act_url in seen_urls:
                continue
            seen_urls.add(act_url)
            results.append(Assignment(
                course_name=course_name,
                title=name,
                activity_type=act_type,
                url=act_url,
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
                        date=_normalize_date(_first_match(post, _DATE_KEYS)),
                        url=post.get("_link", ""),
                        category=board_name,
                        source_site="eclass",
                        body=post.get("_body", ""),
                        attachments=post.get("_attachments", []),
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
                        score_range=item.get("범위", ""),
                        feedback=item.get("피드백", ""),
                    ))
    return results


def _clean_html_text(text: str) -> str:
    """HTML 이스케이프 잔여물과 태그를 정리한다."""
    if not text:
        return ""
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _normalize_syllabus(raw: dict, courses: list[Course]) -> list[SyllabusEntry]:
    """각 과목의 강의계획서(syllabus)를 정규화한다."""
    results = []
    course_map = {c.id: c for c in courses}
    _WEEK_RE = re.compile(r'^(\d{1,2})주차$')

    for course_data in raw.get("courses", []):
        syl = course_data.get("syllabus")
        if not syl or not isinstance(syl, dict):
            continue

        cid = course_data["id"]
        course = course_map.get(cid)
        course_name = course.short_name if course else Course.make_short_name(course_data.get("name", ""))

        textbooks = []
        if "_textbooks" in syl and syl["_textbooks"]:
            for tb in syl["_textbooks"]:
                if isinstance(tb, dict) and tb.get("title"):
                    textbooks.append(SyllabusTextbook(type=tb.get("type", "교재"), title=tb["title"]))
        if not textbooks:
            for ttype in ("주교재", "부교재", "참고교재", "참고서적", "참고도서"):
                title = syl.get(ttype, "").strip()
                if title:
                    textbooks.append(SyllabusTextbook(type=ttype, title=title))

        weekly_plan = []
        seen_weeks: set[int] = set()
        for key, value in syl.items():
            m = _WEEK_RE.match(key)
            if m:
                week_num = int(m.group(1))
                if week_num not in seen_weeks:
                    seen_weeks.add(week_num)
                    weekly_plan.append(SyllabusWeek(week=week_num, topic=value.strip()))
        weekly_plan.sort(key=lambda w: w.week)

        results.append(SyllabusEntry(
            course_name=course_name,
            professor=syl.get("이름", course_data.get("professor", "")),
            email=syl.get("e-mail", ""),
            category=syl.get("이수구분", ""),
            class_type=syl.get("수업방식", ""),
            classroom=syl.get("강의실 / 수업시간", ""),
            office_hours=syl.get("상담시간", ""),
            overview=_clean_html_text(syl.get("강의개요", "")),
            objectives=_clean_html_text(syl.get("강의목표", "")),
            textbooks=textbooks,
            weekly_plan=weekly_plan,
        ))

    return results


# ──────────────────────────────────────────────
#  메인 파이프라인
# ──────────────────────────────────────────────

def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
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
                date=_normalize_date(post.get("date", "")),
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


def _normalize_ndrims_timetable(tt_raw: dict) -> list[TimetableEntry]:
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
        result.append(TimetableEntry(
            course_name=item.get("SBJ_NM", ""),
            course_code=item.get("SBJ_NO", ""),
            professor=item.get("EMP_NM", ""),
            schedule=item.get("TMTBL_KOR_DSC", ""),
            room=item.get("ROOM_KOR_DSC", ""),
            credits=str(item.get("CDT", "")),
            category=item.get("CPDIV_NM", ""),
            campus=item.get("LESN_REGN_CD_NM", ""),
        ))

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
                    date=_normalize_date(post.get("date", "")),
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
    syllabus = _normalize_syllabus(raw, courses)

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
        timetable=ndrims_timetable,
        academic_schedule=academic_schedule,
        syllabus=syllabus,
        grade_history=ndrims_grade_history,
        student_profile=student_profile,
    )

    from normalizer_storage import save_normalized
    from briefing import generate_briefing, print_summary

    save_normalized(output)
    generate_briefing(output)
    print_summary(output)
    return output


