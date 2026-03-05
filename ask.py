"""
school_sync LLM Q&A — 대학 생활 데이터 기반 자연어 질의.

사용법:
  python ask.py                          # 대화 모드
  python ask.py "이번주 과제 뭐 있어?"    # 단일 질문
  python ask.py --refresh                # 데이터 갱신 후 대화
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic
from config import OUTPUT_DIR

NORM_DIR = OUTPUT_DIR / "normalized"

WEEKDAY_KR = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

def _build_system_prompt() -> str:
    today = date.today()
    weekday = WEEKDAY_KR[today.weekday()]
    return f"""당신은 대학생의 학교 생활 데이터를 기반으로 질문에 답하는 어시스턴트입니다.

## 오늘 날짜: {today.isoformat()} ({weekday})

## 규칙
1. 아래 제공된 데이터만을 근거로 답변하세요.
2. 답변 시 반드시 **출처**를 명시하세요. 예: `[출처: 시간표]`, `[출처: 학기별 성적]`
3. 데이터에 없는 정보는 "현재 데이터에 없습니다"라고 명확히 말하세요. 추측하지 마세요.
4. 계산이 필요한 질문(GPA 목표, 남은 학점 등)은 데이터의 숫자를 사용해 단계별로 계산하세요.
5. 답변은 간결하고 실용적으로, 한국어로 해주세요.
6. 날짜/마감 관련은 D-day를 포함하세요.
7. 시간표 질문 시 "오늘"은 {weekday}입니다. schedule 필드에서 "{weekday[0]}" 가 포함된 항목만 필터하세요.

## 계산 참고
- 평점(GPA) = Σ(과목학점 × 과목평점) / Σ(과목학점)
- 평점 등급: A+(4.5), A0(4.0), B+(3.5), B0(3.0), C+(2.5), C0(2.0), D+(1.5), D0(1.0), F(0)
"""


DATA_FILES = {
    "briefing.md": ("오늘의 브리핑", "briefing"),
    "academics/courses.json": ("수강 과목", "academics"),
    "academics/deadlines.json": ("마감 일정", "academics"),
    "academics/assignments.json": ("과제/활동", "academics"),
    "academics/attendance.json": ("출석 기록", "academics"),
    "academics/grades.json": ("eclass 성적", "academics"),
    "schedule/academic_schedule.json": ("학사일정", "schedule"),
    "schedule/calendar.json": ("캘린더", "schedule"),
    "schedule/timetable.json": ("시간표 (nDRIMS)", "schedule"),
    "info/notices.json": ("공지사항", "info"),
    "profile/student.json": ("학적 프로필", "profile"),
    "profile/grade_history.json": ("전체 성적 이력 (nDRIMS)", "profile"),
    "profile/graduation_requirements.json": ("졸업 요건 (데이터사이언스전공 2023학번)", "profile"),
}

QUESTION_CATEGORY_MAP = {
    "과제": ["academics"],
    "마감": ["academics"],
    "출석": ["academics"],
    "결석": ["academics"],
    "성적": ["academics", "profile"],
    "학점": ["academics", "profile"],
    "평점": ["academics", "profile"],
    "GPA": ["academics", "profile"],
    "졸업": ["profile", "schedule"],
    "시간표": ["schedule"],
    "수업": ["schedule", "academics"],
    "강의": ["schedule", "academics"],
    "공지": ["info"],
    "장학": ["info"],
    "학사일정": ["schedule"],
    "개강": ["schedule"],
    "중간": ["schedule"],
    "기말": ["schedule"],
    "수강": ["academics", "schedule"],
    "프로필": ["profile"],
    "학과": ["profile"],
    "학번": ["profile"],
}


def _classify_question(question: str) -> set[str]:
    """질문에서 관련 데이터 카테고리를 추출한다."""
    categories = set()
    for keyword, cats in QUESTION_CATEGORY_MAP.items():
        if keyword in question:
            categories.update(cats)
    if not categories:
        categories = {"briefing", "academics", "profile", "schedule"}
    categories.add("briefing")
    return categories


def _load_context(categories: set[str] | None = None) -> str:
    """normalized 데이터를 LLM 컨텍스트로 로드한다."""
    sections = []

    for rel_path, (label, category) in DATA_FILES.items():
        if categories and category not in categories:
            continue

        path = NORM_DIR / rel_path
        if not path.exists():
            continue

        if rel_path.endswith(".md"):
            content = path.read_text(encoding="utf-8")
            sections.append(f"=== {label} ===\n{content}")
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 50:
                data = data[:50]
                label += " (최근 50건)"
            sections.append(f"=== {label} ===\n{json.dumps(data, ensure_ascii=False, indent=1)}")

    return "\n\n".join(sections)


def _ask(client: Anthropic, question: str, history: list[dict]) -> str:
    """질문을 분류하고, 관련 데이터만 로드하여 Claude에 보낸다."""
    categories = _classify_question(question)
    context = _load_context(categories)

    if not context:
        return "[에러] normalized 데이터가 없습니다. 먼저 python main.py 를 실행하세요."

    history.append({"role": "user", "content": question})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=_build_system_prompt() + "\n\n" + context,
        messages=history,
    )

    answer = response.content[0].text
    history.append({"role": "assistant", "content": answer})
    return answer


def main():
    parser = argparse.ArgumentParser(description="school_sync Q&A")
    parser.add_argument("question", nargs="?", help="질문 (없으면 대화 모드)")
    parser.add_argument("--refresh", action="store_true", help="데이터 갱신 후 시작")
    args = parser.parse_args()

    if args.refresh:
        from normalizer import normalize
        normalize()

    client = Anthropic()
    history = []

    if args.question:
        answer = _ask(client, args.question, history)
        print(answer)
        return

    print("=" * 50)
    print("  school_sync Q&A")
    print("  데이터 기반으로 대학 생활 질문에 답합니다.")
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
            answer = _ask(client, question, history)
            print(f"\n{answer}")
        except Exception as e:
            print(f"\n[에러] {e}")

    print("\n종료.")


if __name__ == "__main__":
    main()
