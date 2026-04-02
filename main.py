"""
school_sync 통합 크롤러 메인 진입점.

사용법:
  python main.py                              # 전체 크롤링 + 정규화
  python main.py --site eclass                # eClass만
  python main.py --site eclass --list         # 수강 과목 목록만
  python main.py --site eclass --scan         # 과목별 구조 분석만
  python main.py --site eclass --course 1 3   # 특정 과목만
  python main.py --site eclass --only syllabus grades  # 특정 데이터만
  python main.py --site eclass --download     # 수업자료 다운로드 포함
  python main.py --site eclass --test         # 첫 과목만 (테스트)
  python main.py --normalize-only             # 정규화 + 컨텍스트 생성만 (이미 raw 있을 때)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from utils import setup_win_encoding
setup_win_encoding()

from browser import create_session
from config import CURRENT_SEMESTER, SITES
from crawlers.eclass.crawler import EclassCrawler, EXTRACTABLE_TYPES
from crawlers.portal import PortalCrawler
from crawlers.department import DepartmentCrawler
from crawlers.ndrims import NdrimsCrawler
from normalizer import normalize
from context_export import export_all as export_context, export_claude_all


CRAWLERS = {
    "eclass": EclassCrawler,
    "portal": PortalCrawler,
    "department": DepartmentCrawler,
    "ndrims": NdrimsCrawler,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"school_sync — 통합 대학 크롤러 ({CURRENT_SEMESTER})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py                              전체 크롤링 + 정규화
  python main.py --site eclass                eClass만
  python main.py --site eclass --list         과목 목록 확인
  python main.py --site eclass --scan         구조 분석만
  python main.py --site eclass --course 1 3   특정 과목
  python main.py --site eclass --only syllabus grades
  python main.py --site eclass --download     수업자료 다운로드
  python main.py --site eclass --test         테스트 (첫 과목)
  python main.py --normalize-only             정규화만 재실행
        """,
    )
    parser.add_argument("--site", nargs="+", metavar="SITE",
                        choices=list(SITES.keys()),
                        help=f"크롤링할 사이트: {', '.join(SITES.keys())}")
    parser.add_argument("--normalize-only", action="store_true",
                        help="크롤링 없이 기존 raw 데이터를 정규화만 수행")
    parser.add_argument("--no-normalize", action="store_true",
                        help="크롤링 후 정규화 단계를 건너뜀")

    eclass_group = parser.add_argument_group("eClass 옵션")
    eclass_group.add_argument("--list", action="store_true",
                              help="수강 과목 목록만 출력")
    eclass_group.add_argument("--scan", action="store_true",
                              help="과목별 구조 분석만 실행")
    eclass_group.add_argument("--course", nargs="+", metavar="FILTER",
                              help="추출할 과목 (번호 또는 이름 키워드)")
    eclass_group.add_argument("--only", nargs="+", metavar="TYPE",
                              choices=EXTRACTABLE_TYPES,
                              help=f"추출 데이터 타입: {', '.join(EXTRACTABLE_TYPES)}")
    eclass_group.add_argument("--download", action="store_true",
                              help="수업자료 파일 다운로드 포함")
    eclass_group.add_argument("--no-calendar", action="store_true",
                              help="캘린더 이벤트 추출 건너뛰기")
    eclass_group.add_argument("--test", action="store_true",
                              help="첫 번째 과목만 추출 (테스트)")

    return parser


def _resolve_sites(args) -> list[str]:
    """실행할 사이트 목록을 결정한다."""
    if args.site:
        return args.site
    return [name for name, cfg in SITES.items() if cfg.get("enabled")]


def _should_normalize(args) -> bool:
    """정규화를 실행해야 하는지 결정한다.
    부분 크롤링(--test, --course)은 semester JSON을 불완전하게 덮어쓰므로
    정규화를 자동 실행하지 않는다. 필요 시 --normalize-only로 별도 실행.
    """
    if args.normalize_only:
        return True
    if args.no_normalize or args.list or args.scan:
        return False
    if args.test or args.course:
        return False
    return True


async def run(args):
    if args.normalize_only:
        normalize()
        export_context()
        export_claude_all()
        return

    sites = _resolve_sites(args)
    if not sites:
        print("[에러] 실행할 사이트가 없습니다. --site 옵션 또는 config.yaml의 enabled를 확인하세요.")
        return

    print("=" * 60)
    print(f"  school_sync — {CURRENT_SEMESTER}")
    print(f"  대상 사이트: {', '.join(sites)}")
    print("=" * 60)

    for site_name in sites:
        if site_name not in CRAWLERS:
            print(f"\n[{site_name}] 아직 구현되지 않은 크롤러입니다. 건너뜁니다.")
            continue

        crawler_cls = CRAWLERS[site_name]
        crawler = crawler_cls()

        session = None
        try:
            headless = site_name != "ndrims"
            session = await create_session(headless=headless, site=site_name)

            if site_name == "eclass":
                await crawler.crawl(
                    session,
                    course_filters=args.course,
                    extract_types=args.only,
                    do_download=args.download,
                    no_calendar=args.no_calendar,
                    test_mode=args.test,
                    list_only=args.list,
                    scan_only=args.scan,
                )
            else:
                await crawler.crawl(session)

        except RuntimeError as e:
            print(f"\n[{site_name}] {e}")
            continue
        finally:
            if session:
                await session.close()

    if _should_normalize(args):
        normalize()
        export_context()
        export_claude_all()

    _write_run_log(sites, args)


def _write_run_log(sites: list[str], args):
    """실행 기록을 output/.last_run.json에 저장한다."""
    from config import OUTPUT_DIR
    log_path = OUTPUT_DIR / ".last_run.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log = {
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "sites": sites,
        "download": getattr(args, "download", False),
        "test_mode": getattr(args, "test", False),
    }

    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run(args))
