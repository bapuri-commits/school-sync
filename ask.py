"""
school_sync LLM Q&A — 대학 생활 데이터 + 웹검색 하이브리드 질의.

사용법:
  python ask.py                          # 대화 모드
  python ask.py "이번주 과제 뭐 있어?"    # 단일 질문
  python ask.py --refresh                # 정규화 재실행 후 대화
  python ask.py --no-search              # 웹검색 비활성화
"""

import argparse
import json
import sys
from datetime import date, timedelta

from utils import setup_win_encoding
setup_win_encoding()

from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic
from config import OUTPUT_DIR

NORM_DIR = OUTPUT_DIR / "normalized"

WEEKDAY_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

MAX_CONTEXT_CHARS = 80_000
MAX_HISTORY_TURNS = 6

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
}

# ──────────────────────────────────────────────
#  데이터 파일 & 카테고리
# ──────────────────────────────────────────────

DATA_FILES = {
    "briefing.md":                            ("오늘의 브리핑",                    "briefing",  10),
    "academics/courses.json":                 ("수강 과목",                        "academics", 20),
    "academics/deadlines.json":               ("마감 일정",                        "academics", 15),
    "academics/assignments.json":             ("과제/활동",                        "academics", 18),
    "academics/attendance.json":              ("출석 기록",                        "academics", 40),
    "academics/grades.json":                  ("eclass 성적",                      "academics", 30),
    "academics/syllabus.json":                ("강의계획서 (교재/수업계획/교수 정보)", "syllabus",  25),
    "schedule/academic_schedule.json":        ("학사일정",                         "schedule",  35),
    "schedule/calendar.json":                 ("캘린더",                           "schedule",  38),
    "schedule/timetable.json":                ("시간표 (nDRIMS)",                  "schedule",  12),
    "info/notices.json":                      ("공지사항",                         "info",      45),
    "profile/student.json":                   ("학적 프로필 (이름/학과/학점)",       "profile",   5),
    "profile/grade_history.json":             ("전체 성적 이력 (nDRIMS)",           "profile",   50),
    "curriculum/curriculum.md":               ("교육과정/졸업요건/이수체계",          "curriculum", 8),
}

# [LEGACY] 키워드 매칭 기반 분류 — LLM 분류 실패 시 fallback으로 사용
# QUESTION_CATEGORY_MAP = {
#     "과제": ["academics"], "마감": ["academics"], "출석": ["academics"],
#     "결석": ["academics"], "퀴즈": ["academics"], "리포트": ["academics"],
#     "레포트": ["academics"], "제출": ["academics"],
#     "성적": ["academics", "profile"], "학점": ["academics", "profile"],
#     "평점": ["academics", "profile"], "GPA": ["academics", "profile"],
#     "졸업": ["profile", "schedule"], "프로필": ["profile"],
#     "학과": ["profile"], "학번": ["profile"], "이수": ["profile"],
#     "시간표": ["schedule"], "캘린더": ["schedule"], "일정": ["schedule"],
#     "학사일정": ["schedule"], "개강": ["schedule"], "종강": ["schedule"],
#     "방학": ["schedule"], "휴강": ["schedule"], "보강": ["schedule"],
#     "중간고사": ["schedule"], "기말고사": ["schedule"],
#     "중간": ["schedule"], "기말": ["schedule"],
#     "시험": ["schedule", "syllabus"],
#     "수강": ["academics", "schedule"], "수업": ["schedule", "academics"],
#     "공지": ["info"], "장학": ["info"], "안내": ["info"],
#     "공모전": ["info"], "특강": ["info"],
#     "교재": ["syllabus"], "교과서": ["syllabus"], "책": ["syllabus"],
#     "강의계획": ["syllabus"], "수업계획": ["syllabus"],
#     "실습": ["syllabus", "academics"], "교수": ["syllabus", "academics"],
#     "이메일": ["syllabus"], "상담": ["syllabus"], "주차": ["syllabus"],
#     "강의실": ["syllabus", "schedule"],
#     "강의개요": ["syllabus"], "강의목표": ["syllabus"],
#     "강의": ["syllabus", "schedule"],
# }

_AVAILABLE_CATEGORIES = sorted({cat for _, cat, _ in DATA_FILES.values()})

_BRIEFING_RELEVANT = {"academics", "schedule", "info"}

_file_cache: dict[str, object] = {}
_course_names_cache: list[str] | None = None

# ──────────────────────────────────────────────
#  System Prompt
# ──────────────────────────────────────────────

def _build_system_prompt(web_search_enabled: bool = True) -> str:
    today = date.today()
    weekday = WEEKDAY_KR[today.weekday()]

    search_rules = """
5. 학교 데이터에 없지만 웹검색으로 보완할 수 있는 질문이면 web_search 도구를 사용하세요.
6. 웹검색 결과를 사용한 경우 `[출처: 웹검색]`과 URL을 명시하세요.
7. 학교 데이터와 웹검색 결과가 모두 있으면 학교 데이터를 우선하세요.""" if web_search_enabled else """
5. 데이터에 없는 정보는 "현재 데이터에 없습니다"라고 명확히 말하세요. 추측하지 마세요."""

    return f"""당신은 대학생의 학교 생활 데이터를 기반으로 질문에 답하는 어시스턴트입니다.

## 오늘 날짜: {today.isoformat()} ({weekday})

## 규칙
1. 아래 제공된 학교 데이터를 우선 참조하세요.
2. 답변 시 반드시 **출처**를 명시하세요. 예: `[출처: 시간표]`, `[출처: 학기별 성적]`
3. 계산이 필요한 질문(GPA 목표, 남은 학점 등)은 데이터의 숫자를 사용해 단계별로 계산하세요.
4. 답변은 간결하고 실용적으로, 한국어로 해주세요.{search_rules}

## 시간표
- "오늘"은 {weekday}. timetable schedule 필드에서 "{weekday[0]}"가 포함된 항목 필터.
- 형식 예시: `"월 5교시(13:00) ~ 6.5교시(15:00)"`, `"화 1교시(09:00) ~ 2.5교시(11:00), 목 1교시(09:00) ~ 2.5교시(11:00)"`

## 계산 참고
- 평점(GPA) = Σ(과목학점 × 과목평점) / Σ(과목학점)
- 평점 등급: A+(4.5), A0(4.0), B+(3.5), B0(3.0), C+(2.5), C0(2.0), D+(1.5), D0(1.0), F(0)
"""

# ──────────────────────────────────────────────
#  질문 분류
# ──────────────────────────────────────────────

_CATEGORY_DESCRIPTIONS = {
    "academics": "수강 과목, 과제, 마감, 출석, 성적, 퀴즈, 제출",
    "briefing": "오늘의 브리핑, 일일 요약",
    "curriculum": "교육과정, 졸업요건, 이수체계, 필수과목, 전공학점, 교양학점, 마이크로디그리, 선후수과목",
    "info": "공지사항, 장학, 안내, 공모전, 특강",
    "profile": "학적 프로필, 전체 성적 이력, 학과, 학번, GPA",
    "schedule": "시간표, 캘린더, 학사일정, 개강, 종강, 시험, 중간/기말",
    "syllabus": "강의계획서, 교재, 교수 정보, 수업 주차, 강의개요/목표",
}


def _classify_question(question: str) -> tuple[set[str], str | None]:
    """키워드 기반 질문 분류 + 과목명 직접 매칭.

    Returns:
        (categories, mentioned_course): 카테고리 집합과 언급된 과목명(없으면 None).
    """
    categories, _ = _classify_question_keyword(question)
    course_names = _get_course_names()
    for name in course_names:
        if name in question:
            return categories, name
    return categories, None


def _classify_question_llm(question: str, client) -> tuple[set[str], str | None]:
    course_names = _get_course_names()
    cat_list = "\n".join(
        f"- {cat}: {_CATEGORY_DESCRIPTIONS.get(cat, '')}"
        for cat in _AVAILABLE_CATEGORIES
    )
    prompt = (
        "다음 질문을 분류해줘. 아래 형식의 JSON으로만 응답해.\n"
        "다른 텍스트, 설명, 마크다운 없이 JSON만 출력해.\n\n"
        f"카테고리 목록:\n{cat_list}\n\n"
        f"수강 과목 목록: {course_names}\n\n"
        f"질문: {question}\n\n"
        '출력 형식:\n'
        '{\n'
        '  "categories": ["academics", "briefing"],\n'
        '  "mentioned_course": "알고리즘및실습"  // 과목 언급 없으면 null\n'
        '}'
    )
    resp = client.messages.create(
        model="claude-haiku-3-5-20241022",
        max_tokens=150,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    parsed = json.loads(text)
    categories = {c for c in parsed.get("categories", []) if c in _AVAILABLE_CATEGORIES}
    if not categories:
        categories = {"briefing", "academics", "profile", "schedule"}
    if categories & _BRIEFING_RELEVANT:
        categories.add("briefing")
    mentioned_course = parsed.get("mentioned_course") or None
    return categories, mentioned_course


def _classify_question_keyword(question: str) -> tuple[set[str], None]:
    """[LEGACY] 키워드 매칭 기반 fallback 분류. 과목 추출은 None 반환."""
    keyword_map = {
        "과제": ["academics"], "마감": ["academics"], "출석": ["academics"],
        "결석": ["academics"], "퀴즈": ["academics"], "리포트": ["academics"],
        "레포트": ["academics"], "제출": ["academics"],
        "성적": ["academics", "profile"], "학점": ["academics", "profile"],
        "평점": ["academics", "profile"], "GPA": ["academics", "profile"],
        "졸업": ["curriculum", "profile"], "프로필": ["profile"],
        "학과": ["profile"], "학번": ["profile"], "이수": ["curriculum", "profile"],
        "교육과정": ["curriculum"], "커리큘럼": ["curriculum"], "필수과목": ["curriculum"],
        "전공학점": ["curriculum"], "교양학점": ["curriculum"], "선수과목": ["curriculum"],
        "후수과목": ["curriculum"], "이수체계": ["curriculum"], "졸업요건": ["curriculum"],
        "마이크로디그리": ["curriculum"], "TOEIC": ["curriculum"],
        "종합설계": ["curriculum"], "심화과정": ["curriculum"],
        "시간표": ["schedule"], "캘린더": ["schedule"], "일정": ["schedule"],
        "학사일정": ["schedule"], "개강": ["schedule"], "종강": ["schedule"],
        "방학": ["schedule"], "휴강": ["schedule"], "보강": ["schedule"],
        "중간고사": ["schedule", "syllabus"], "기말고사": ["schedule", "syllabus"],
        "중간": ["schedule", "syllabus"], "기말": ["schedule", "syllabus"],
        "시험": ["schedule", "syllabus"],
        "수강": ["academics", "schedule"], "수업": ["schedule", "academics"],
        "공지": ["info"], "장학": ["info"], "안내": ["info"],
        "공모전": ["info"], "특강": ["info"],
        "교재": ["syllabus"], "교과서": ["syllabus"], "책": ["syllabus"],
        "강의계획": ["syllabus"], "수업계획": ["syllabus"],
        "실습": ["syllabus", "academics"], "교수": ["syllabus", "academics"],
        "이메일": ["syllabus"], "상담": ["syllabus"], "주차": ["syllabus"],
        "강의실": ["syllabus", "schedule"],
        "강의개요": ["syllabus"], "강의목표": ["syllabus"],
        "강의": ["syllabus", "schedule"],
    }
    categories = set()
    for keyword, cats in keyword_map.items():
        if keyword in question:
            categories.update(cats)

    if "강의" in question and categories:
        syllabus_clues = ("계획", "개요", "목표", "교수", "교재", "주차", "이수", "상담")
        schedule_clues = ("시간", "실", "장소", "몇 시", "언제", "오늘", "내일")
        has_syllabus = any(w in question for w in syllabus_clues)
        has_schedule = any(w in question for w in schedule_clues)
        if has_syllabus and not has_schedule:
            categories.discard("schedule")
        elif has_schedule and not has_syllabus:
            categories.discard("syllabus")

    if not categories:
        categories = {"briefing", "academics", "profile", "schedule"}
    if categories & _BRIEFING_RELEVANT:
        categories.add("briefing")
    return categories, None


def _extract_course_names(question: str, context_courses: list[str]) -> list[str]:
    """질문에서 언급된 과목명을 추출한다."""
    matched = []
    for name in context_courses:
        if name in question:
            matched.append(name)
    return matched

# ──────────────────────────────────────────────
#  컨텍스트 로드 (토큰 예산 + 스마트 필터링)
# ──────────────────────────────────────────────

# 파일 캐시 — 프로세스 생애 1회만 디스크에서 읽는다.
_file_cache: dict[str, str | list | dict] = {}


def _load_file(path, rel_path: str):
    """파일을 읽어 캐시에 저장하고 반환한다."""
    if rel_path not in _file_cache:
        if rel_path.endswith(".md"):
            _file_cache[rel_path] = path.read_text(encoding="utf-8")
        else:
            _file_cache[rel_path] = json.loads(path.read_text(encoding="utf-8"))
    return _file_cache[rel_path]


def _get_course_names() -> list[str]:
    """courses.json에서 과목명 목록을 가져온다."""
    rel_path = "academics/courses.json"
    path = NORM_DIR / rel_path
    if not path.exists():
        return []
    try:
        courses = _load_file(path, rel_path)
        return [c.get("short_name", c.get("name", "")) for c in courses]
    except Exception:
        return []


def _detect_course(question: str) -> str | None:
    """질문에서 수강 과목명을 감지한다."""
    for name in _get_course_names():
        if name in question:
            return name
    return None


def _smart_filter(rel_path: str, data: list, question: str, course_names: list[str],
                  mentioned_course: str | None = None) -> list:
    """리스트 데이터를 질문 관련성으로 필터링한다.

    Args:
        mentioned_course: LLM이 추출한 과목명. None이면 키워드 fallback으로 추출.
    """
    if mentioned_course is not None:
        mentioned = [mentioned_course]
    else:
        # [LEGACY] 키워드 기반 과목 추출 — LLM 분류 실패 시 fallback
        mentioned = _extract_course_names(question, course_names)

    if "notices" in rel_path:
        if mentioned:
            filtered = [n for n in data if any(m in n.get("course_name", "") or m in n.get("title", "") for m in mentioned)]
            if filtered:
                return filtered
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        recent = [n for n in data if n.get("date", "") >= week_ago]
        return recent if recent else data[:20]

    if "attendance" in rel_path:
        if mentioned:
            return [a for a in data if any(m in a.get("course_name", "") for m in mentioned)]
        abnormal = [a for a in data if a.get("status") in ("결석", "지각", "조퇴", "유고결석")]
        return abnormal if abnormal else data

    if "grades" in rel_path and "grade_history" not in rel_path:
        if mentioned:
            return [g for g in data if any(m in g.get("course_name", "") for m in mentioned)]
        return data

    if "academic_schedule" in rel_path:
        today_iso = date.today().isoformat()
        month_later = (date.today() + timedelta(days=30)).isoformat()
        upcoming = [s for s in data
                     if s.get("end_date", s.get("start_date", "")) >= today_iso
                     and s.get("start_date", "") <= month_later]
        return upcoming if upcoming else data[:20]

    if "grade_history" in rel_path:
        if mentioned:
            return [g for g in data if any(m in g.get("course_name", "") for m in mentioned)]
        return data

    if isinstance(data, list) and len(data) > 50:
        return data[:50]

    return data


def _load_context(categories: set[str],
                  question: str = "",
                  max_chars: int = MAX_CONTEXT_CHARS,
                  mentioned_course: str | None = None) -> str:
    """카테고리에 해당하는 데이터를 우선순위 순으로 토큰 예산 내에서 로드한다."""
    course_names = _get_course_names()

    candidates = []
    for rel_path, (label, category, priority) in DATA_FILES.items():
        if category not in categories:
            continue
        path = NORM_DIR / rel_path
        if not path.exists():
            continue
        candidates.append((priority, rel_path, label, path))

    candidates.sort(key=lambda x: x[0])

    sections = []
    total_chars = 0

    for priority, rel_path, label, path in candidates:
        raw = _load_file(path, rel_path)

        if rel_path.endswith(".md"):
            section = f"=== {label} ===\n{raw}"
        else:
            # 캐시 원본을 보호하기 위해 얕은 복사
            data = list(raw) if isinstance(raw, list) else dict(raw) if isinstance(raw, dict) else raw
            if isinstance(data, list) and question:
                data = _smart_filter(rel_path, data, question, course_names,
                                     mentioned_course=mentioned_course)
            if isinstance(data, list) and len(data) == 0:
                continue
            if "student" in rel_path:
                if isinstance(data, list):
                    data = [
                        {k: v for k, v in item.items() if k not in ("phone", "email")}
                        if isinstance(item, dict) else item
                        for item in data
                    ]
                elif isinstance(data, dict):
                    data = {k: v for k, v in data.items() if k not in ("phone", "email")}
            section = f"=== {label} ===\n{json.dumps(data, ensure_ascii=False, indent=1)}"

        if total_chars + len(section) > max_chars and sections:
            break

        sections.append(section)
        total_chars += len(section)

    return "\n\n".join(sections)

# ──────────────────────────────────────────────
#  Claude API 호출 (웹검색 agentic loop)
# ──────────────────────────────────────────────

def _extract_text(response) -> str:
    """응답에서 텍스트 블록을 추출한다."""
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)


def _trim_history(history: list[dict]) -> list[dict]:
    """최근 N턴만 유지하여 토큰 폭주를 방지한다."""
    max_items = MAX_HISTORY_TURNS * 2
    if len(history) > max_items:
        return history[-max_items:]
    return history


def _ask(client: Anthropic, question: str, history: list[dict],
         web_search: bool = True) -> str:
    categories, mentioned_course = _classify_question(question)
    context = _load_context(categories, question=question, mentioned_course=mentioned_course)

    if not context:
        msg = "[에러] normalized 데이터가 없습니다. 먼저 python main.py 를 실행하세요."
        print(msg)
        return msg

    system = [
        {
            "type": "text",
            "text": _build_system_prompt(web_search_enabled=web_search) + "\n\n" + context,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    today = date.today()
    weekday = WEEKDAY_KR[today.weekday()]
    tagged_question = f"[오늘: {today.isoformat()} {weekday}] {question}"
    history.append({"role": "user", "content": tagged_question})
    trimmed = _trim_history(history)

    tools = [WEB_SEARCH_TOOL] if web_search else None

    kwargs = dict(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        messages=trimmed,
        temperature=0,
    )
    if tools:
        kwargs["tools"] = tools

    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        response = stream.get_final_message()
    print()

    rounds = 0
    while response.stop_reason == "tool_use" and rounds < 5:
        rounds += 1
        history.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "웹검색이 서버에서 처리되었습니다.",
                })

        if tool_results:
            history.append({"role": "user", "content": tool_results})

        kwargs["messages"] = _trim_history(history)
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
            response = stream.get_final_message()
        print()

    answer = _extract_text(response)
    history.append({"role": "assistant", "content": response.content})
    return answer

# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="school_sync Q&A")
    parser.add_argument("question", nargs="?", help="질문 (없으면 대화 모드)")
    parser.add_argument("--refresh", action="store_true",
                        help="기존 raw 데이터를 다시 정규화한 뒤 대화 시작 (크롤링은 하지 않음)")
    parser.add_argument("--no-search", action="store_true", help="웹검색 비활성화")
    args = parser.parse_args()

    if args.refresh:
        from normalizer import normalize
        normalize()

    client = Anthropic()
    history = []
    web_search = not args.no_search

    if args.question:
        _ask(client, args.question, history, web_search=web_search)
        return

    search_label = "웹검색 ON" if web_search else "웹검색 OFF"
    print("=" * 50)
    print(f"  school_sync Q&A ({search_label})")
    print("  학교 데이터 + 웹검색 하이브리드 질의")
    print("  'q' 또는 '종료'로 나갈 수 있습니다.")
    print("=" * 50)

    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question:
            continue
        if question in ("q", "quit", "exit", "종료"):
            break

        try:
            print()
            _ask(client, question, history, web_search=web_search)
        except Exception as e:
            print(f"\n[에러] {e}")

    print("\n종료.")


if __name__ == "__main__":
    main()
