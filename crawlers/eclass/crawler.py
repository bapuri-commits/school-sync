"""
EclassCrawler — 기존 eclass_crawler/main.py의 파이프라인을
BaseCrawler 인터페이스로 감싼 클래스.
"""

import asyncio
import re
import traceback
from datetime import datetime
from pathlib import Path

from browser import BrowserSession
from config import CURRENT_SEMESTER, REQUEST_DELAY, OUTPUT_DIR
from utils import save_json

from crawlers.base import BaseCrawler
from crawlers.eclass.scanner import scan_course, CourseScan
from crawlers.eclass.extractors.courses import extract_courses
from crawlers.eclass.extractors.syllabus import extract_syllabus
from crawlers.eclass.extractors.grades import extract_grades
from crawlers.eclass.extractors.attendance import extract_attendance
from crawlers.eclass.extractors.notices import extract_boards
from crawlers.eclass.extractors.assignments import extract_assignments
from crawlers.eclass.extractors.calendar import extract_calendar_events
from crawlers.eclass.extractors.materials import download_materials

RAW_DIR = OUTPUT_DIR / "raw" / "eclass"
COURSES_DIR = RAW_DIR / "courses"

FEATURE_EXTRACTORS = {
    "syllabus": ("강의계획서", extract_syllabus),
    "grades": ("성적", extract_grades),
    "attendance": ("출석", extract_attendance),
    "boards": ("게시판", extract_boards),
    "activities": ("활동/과제", extract_assignments),
}

EXTRACTABLE_TYPES = list(FEATURE_EXTRACTORS.keys()) + ["materials"]


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'\s*-\s*\d+분반.*$', '', name)
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name).strip('_')
    return name[:80]


def _filter_courses(courses: list[dict], filters: list[str]) -> list[dict]:
    selected = []
    for f in filters:
        if f.isdigit():
            idx = int(f) - 1
            if 0 <= idx < len(courses):
                if courses[idx] not in selected:
                    selected.append(courses[idx])
            else:
                print(f"  [경고] 과목 번호 {f}: 범위 초과 (1~{len(courses)})")
        else:
            for c in courses:
                if f.lower() in c["name"].lower() and c not in selected:
                    selected.append(c)
    return selected


class EclassCrawler(BaseCrawler):
    site_name = "eclass"

    def requires_auth(self) -> bool:
        return True

    async def crawl(
        self,
        session: BrowserSession,
        *,
        course_filters: list[str] | None = None,
        extract_types: list[str] | None = None,
        do_download: bool = False,
        no_calendar: bool = False,
        test_mode: bool = False,
        list_only: bool = False,
        scan_only: bool = False,
    ) -> dict:
        page = session.page

        courses = await extract_courses(page)
        if not courses:
            print("[에러] 수강 과목을 찾지 못했습니다.")
            return {"error": "no_courses"}

        if list_only:
            print("\n  수강 과목 목록:")
            for i, c in enumerate(courses, 1):
                print(f"    {i}. [{c['id']}] {c['name']} ({c.get('professor', '')})")
            return {"courses": courses}

        if course_filters:
            courses = _filter_courses(courses, course_filters)
            if not courses:
                print("[에러] 조건에 맞는 과목이 없습니다.")
                return {"error": "no_matching_courses"}
            print(f"\n[선택] {len(courses)}개 과목:")
            for c in courses:
                print(f"  - {c['name']}")

        if test_mode:
            courses = courses[:1]
            print(f"\n[테스트 모드] 첫 번째 과목만: {courses[0]['name']}")

        # Phase 1: 구조 분석
        print(f"\n--- Phase 1: 구조 분석 ({len(courses)}개 과목) ---")
        scans: dict[int, CourseScan] = {}
        for course in courses:
            try:
                scan = await scan_course(page, course["id"], course["name"])
                scans[course["id"]] = scan
            except Exception as e:
                print(f"  [에러] 스캔 실패 ({course['name']}): {e}")
            await asyncio.sleep(REQUEST_DELAY)

        extract_plan = extract_types or (
            list(FEATURE_EXTRACTORS.keys()) + (["materials"] if do_download else [])
        )
        self._print_scan_summary(courses, scans, extract_plan)

        scan_output = {
            "semester": CURRENT_SEMESTER,
            "scanned_at": datetime.now().isoformat(),
            "courses": {str(cid): s.to_dict() for cid, s in scans.items()},
        }
        save_json(scan_output, RAW_DIR / "scan_result.json")

        if scan_only:
            print(f"\n  스캔 결과 저장: {RAW_DIR / 'scan_result.json'}")
            return scan_output

        # Phase 2: 데이터 추출
        calendar_events = []
        if not no_calendar and session.sesskey:
            try:
                calendar_events = await extract_calendar_events(
                    session.cookies_dict, session.sesskey
                )
            except Exception as e:
                print(f"  [에러] 캘린더 추출 실패: {e}")

        print(f"\n--- Phase 2: 데이터 추출 ---")
        course_data = []
        failed = []

        for course in courses:
            scan = scans.get(course["id"])
            if not scan:
                failed.append(course["name"])
                continue

            try:
                data = await self._extract_course(
                    session, course, scan, extract_types, do_download
                )
                course_data.append(data)

                filename = f"{_sanitize_filename(data['name'])}.json"
                course_output = {
                    "semester": CURRENT_SEMESTER,
                    "extracted_at": datetime.now().isoformat(),
                    **data,
                }
                save_json(course_output, COURSES_DIR / filename)
                print(f"  -> 저장: courses/{filename}")

            except Exception as e:
                print(f"  [에러] 과목 추출 실패 ({course['name']}): {e}")
                traceback.print_exc()
                failed.append(course["name"])

        full_result = {
            "semester": CURRENT_SEMESTER,
            "extracted_at": datetime.now().isoformat(),
            "course_count": len(course_data),
            "failed_courses": failed,
            "calendar_events": calendar_events,
            "courses": course_data,
        }
        full_path = RAW_DIR / f"{CURRENT_SEMESTER}_semester.json"
        save_json(full_result, full_path)

        print(f"\n{'='*60}")
        print(f"  완료!")
        print(f"  성공: {len(course_data)}개 과목")
        if failed:
            print(f"  실패: {len(failed)}개 ({', '.join(failed)})")
        print(f"  통합 JSON: {full_path}")
        print(f"  과목별 JSON: {COURSES_DIR}/")
        if calendar_events:
            print(f"  캘린더 이벤트: {len(calendar_events)}개")
        if do_download:
            print(f"  다운로드 폴더: output/downloads/")
        print(f"{'='*60}")

        return full_result

    async def _extract_course(
        self, session: BrowserSession, course: dict, scan: CourseScan,
        extract_types: list[str] | None, do_download: bool,
    ) -> dict:
        cid = course["id"]
        print(f"\n{'='*50}")
        print(f"  과목: {course['name']} (id={cid})")
        print(f"{'='*50}")

        page = session.page
        result = {
            "id": cid,
            "name": course["name"],
            "professor": course.get("professor", ""),
            "url": course.get("url", ""),
            "scan": scan.to_dict(),
        }

        if extract_types:
            targets = [t for t in extract_types if t in FEATURE_EXTRACTORS]
        else:
            targets = list(FEATURE_EXTRACTORS.keys())

        for key in targets:
            label, extractor_fn = FEATURE_EXTRACTORS[key]
            if not scan.has(key) and key != "activities":
                print(f"  [SKIP] {label}: 이 과목에 없음")
                continue
            try:
                if key == "boards":
                    result[key] = await extractor_fn(page, cid, scanned_boards=scan.boards)
                else:
                    result[key] = await extractor_fn(page, cid)
            except Exception as e:
                print(f"  [에러] {label} 추출 실패 (course={cid}): {e}")
                result[key] = {"_error": str(e)}
            await asyncio.sleep(REQUEST_DELAY)

        if do_download or (extract_types and "materials" in extract_types):
            if scan.downloadable_resources:
                try:
                    dl_results = await download_materials(
                        page, cid, course["name"], scan.downloadable_resources
                    )
                    result["downloaded_materials"] = dl_results
                except Exception as e:
                    print(f"  [에러] 자료 다운로드 실패: {e}")
                    result["downloaded_materials"] = {"_error": str(e)}
            else:
                print(f"  [SKIP] 수업자료: 다운로드 가능한 리소스 없음")

        return result

    def _print_scan_summary(
        self, courses: list[dict], scans: dict[int, CourseScan], extract_plan: list[str],
    ):
        print(f"\n{'='*60}")
        print(f"  스캔 결과 요약 (추출 계획)")
        print(f"{'='*60}")
        for course in courses:
            scan = scans.get(course["id"])
            if not scan:
                print(f"\n  [{course['id']}] {course['name']} - 스캔 실패")
                continue

            will_extract = []
            will_skip = []
            for key in extract_plan:
                if key == "materials":
                    if scan.downloadable_resources:
                        will_extract.append(f"자료다운({len(scan.downloadable_resources)})")
                    else:
                        will_skip.append("자료다운(없음)")
                elif key in FEATURE_EXTRACTORS:
                    label = FEATURE_EXTRACTORS[key][0]
                    if scan.has(key) or key == "activities":
                        will_extract.append(label)
                    else:
                        will_skip.append(f"{label}(없음)")

            print(f"\n  [{course['id']}] {course['name']}")
            print(f"    추출: {', '.join(will_extract) if will_extract else '없음'}")
            if will_skip:
                print(f"    건너뜀: {', '.join(will_skip)}")
            if scan.boards:
                print(f"    게시판: {', '.join(b['name'] for b in scan.boards)}")
        print(f"{'='*60}")
