"""
school_sync ask.py 일관성 검증 스크립트.

같은 질문을 N회 반복 호출해서 답변이 일관된지 확인한다.

사용법:
  python test_consistency.py
  python test_consistency.py --runs 3       # 반복 횟수 변경
  python test_consistency.py --no-search    # 웹검색 비활성화
"""

import argparse
import sys

from utils import setup_win_encoding
setup_win_encoding()

from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic
from ask import _ask

COMPARE_CHARS = 100

TEST_QUESTIONS = [
    "이번주 과제 뭐 있어?",
    "다음 시험 언제야?",
    "오늘 수업 있어?",
    "성적 어떻게 돼?",
    "이번 학기 수강 과목 알려줘",
]


def run_consistency_test(runs: int = 5, web_search: bool = True):
    client = Anthropic()

    consistent_count = 0
    total = len(TEST_QUESTIONS)

    print("=" * 60)
    print(f"  school_sync 일관성 테스트 (반복 {runs}회, 웹검색={'ON' if web_search else 'OFF'})")
    print("=" * 60)

    for q_idx, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n[{q_idx}/{total}] 질문: {question}")
        print("-" * 60)

        answers = []
        for run in range(1, runs + 1):
            try:
                answer = _ask(client, question, history=[], web_search=web_search)
                snippet = answer[:COMPARE_CHARS].replace("\n", " ")
                answers.append(snippet)
                print(f"  #{run}: {snippet}")
            except Exception as e:
                print(f"  #{run}: [에러] {e}")
                answers.append(f"[에러] {e}")

        unique = set(answers)
        if len(unique) == 1:
            print(f"  → ✓ 일관됨")
            consistent_count += 1
        else:
            print(f"  → ✗ [불일치] {len(unique)}가지 답변 패턴 감지")

    print("\n" + "=" * 60)
    print(f"  일관성: {consistent_count}/{total} 질문")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="ask.py 일관성 검증")
    parser.add_argument("--runs", type=int, default=5, help="반복 횟수 (기본: 5)")
    parser.add_argument("--no-search", action="store_true", help="웹검색 비활성화")
    args = parser.parse_args()

    run_consistency_test(runs=args.runs, web_search=not args.no_search)


if __name__ == "__main__":
    main()
