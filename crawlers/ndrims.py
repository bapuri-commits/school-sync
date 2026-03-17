"""
nDRIMS 크롤러 — 학적 프로필, 전체 성적, 개인 시간표 추출.
SSO 로그인 필요. CLX 프레임워크 기반 SPA.

CLX UI의 메뉴를 JS로 클릭하고, 발생하는 API 응답을 가로채서 JSON 데이터를 수집한다.
"""

import asyncio
import json
from pathlib import Path

from browser import BrowserSession
from config import OUTPUT_DIR, SITES
from crawlers.base import BaseCrawler
from utils import save_json

RAW_DIR = OUTPUT_DIR / "raw" / "ndrims"
BASE_URL = SITES.get("ndrims", {}).get("base_url", "https://ndrims.dongguk.edu")


async def _click_menu(page, label: str):
    """CLX .cl-text 메뉴 항목을 JS로 클릭한다."""
    return await page.evaluate("""
        (label) => {
            const els = document.querySelectorAll('.cl-text');
            for (const el of els) {
                if (el.innerText.trim() === label) {
                    const target = el.closest('.cl-menu-item') || el.closest('.cl-folder') || el.parentElement;
                    if (target) { target.click(); return true; }
                }
            }
            return false;
        }
    """, label)


async def _dismiss_popups(page):
    """CLX HTML 팝업(confirm/alert 오버레이)을 닫는다."""
    for _ in range(3):
        try:
            closed = await page.evaluate("""
                () => {
                    let closed = 0;
                    document.querySelectorAll(
                        '.cl-messagedialog button, .cl-confirm button, .cl-alert button, ' +
                        '[class*="dialog"] button, [class*="popup"] button, [class*="modal"] button'
                    ).forEach(btn => {
                        const text = btn.innerText.trim();
                        if (text === '확인' || text === 'OK' || text === '닫기' || text === '예') {
                            btn.click(); closed++;
                        }
                    });
                    return closed;
                }
            """)
            if closed == 0:
                break
            await asyncio.sleep(0.5)
        except Exception:
            break


async def _wait_for_clx(page, timeout: float = 10):
    """CLX 컴포넌트가 렌더링될 때까지 대기한다."""
    for _ in range(int(timeout * 2)):
        count = await page.evaluate("() => document.querySelectorAll('.cl-text').length")
        if count > 20:
            return count
        await asyncio.sleep(0.5)
    return 0


async def _capture_apis(page, folder: str, submenu: str, api_keywords: list[str], wait_sec: float = 5) -> dict:
    """폴더 메뉴 → 서브메뉴 클릭 후 API 응답을 캡처한다."""
    captured = {}

    async def on_response(response):
        url = response.url
        for kw in api_keywords:
            if kw in url:
                try:
                    body = await response.json()
                    captured[kw] = body
                except Exception:
                    pass

    page.on("response", on_response)

    await _wait_for_clx(page)

    await _click_menu(page, folder)
    await asyncio.sleep(2)
    await _dismiss_popups(page)

    clicked = await _click_menu(page, submenu)
    if not clicked:
        await asyncio.sleep(2)
        clicked = await _click_menu(page, submenu)
    if not clicked:
        visible = await page.evaluate("() => document.querySelectorAll('.cl-text').length")
        print(f"    '{submenu}' 못 찾음 (cl-text {visible}개)")

    await asyncio.sleep(wait_sec)
    await _dismiss_popups(page)

    page.remove_listener("response", on_response)
    return captured


class NdrimsCrawler(BaseCrawler):
    site_name = "ndrims"

    def requires_auth(self) -> bool:
        return True

    async def crawl(self, session: BrowserSession, **opts) -> dict:
        page = session.page
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        print(f"  [nDRIMS] 메인 페이지 대기...")
        await asyncio.sleep(3)
        await _dismiss_popups(page)

        result = {}

        # === 1. 학적 프로필 ===
        print(f"\n  [1/3] 학적 프로필...")
        profile_apis = [
            "EdbStdSearchP10/doList",
            "EdbStud010/doList",
            "EdbStdInfo/doList",
        ]
        profile_data = await _capture_apis(page, "학적/확인서", "학적부열람", profile_apis, wait_sec=5)

        profile = {}
        for key, data in profile_data.items():
            if "EdbStdSearchP10" in key:
                items = data.get("dsMain", [])
                if items:
                    profile["student_search"] = items[0]
            elif "EdbStud010" in key:
                items = data.get("dsMainBas", [])
                if items:
                    profile["student_detail"] = items[0]
            elif "EdbStdInfo" in key:
                items = data.get("dsMain", [])
                if items:
                    profile["student_info"] = items[0]

        if profile:
            result["profile"] = profile
            s = profile.get("student_search", {})
            print(f"    {s.get('STD_NM', '?')} | {s.get('MJR_NM', '?')} {s.get('SCHGRD', '?')}학년 | "
                  f"평점 {s.get('TT_MRKS_AVG', '?')} | {s.get('ACQ_PNT', '?')}학점")
        else:
            print(f"    프로필 추출 실패")

        # === 2. 전체 성적 ===
        print(f"\n  [2/3] 전체 성적 조회...")
        grade_apis = [
            "EddRec",
            "doListSemCd",
        ]
        grade_data = await _capture_apis(page, "성적", "전체성적조회", grade_apis, wait_sec=5)

        grades_raw = {}
        for key, data in grade_data.items():
            if "EddRec" in key:
                grades_raw["grades"] = data
            elif "SemCd" in key:
                grades_raw["semesters"] = data

        if grades_raw:
            result["grades"] = grades_raw
            grade_list = []
            for k, v in grades_raw.get("grades", {}).items():
                if isinstance(v, list):
                    grade_list.extend(v)
            print(f"    성적 데이터: {len(grade_list)}건")
        else:
            print(f"    성적 데이터 없음 (조회 기간 제한일 수 있음)")

        # === 3. 졸업 이수 현황 ===
        print(f"\n  [3/4] 졸업 이수 현황...")
        grad_apis = [
            "EdbGrad",
            "EddGrad",
            "doList",
            "doLoad",
        ]
        grad_data = await _capture_apis(page, "졸업", "졸업이수현황", grad_apis, wait_sec=5)

        if not grad_data:
            grad_data = await _capture_apis(page, "졸업", "졸업사정표", grad_apis, wait_sec=5)

        if grad_data:
            result["graduation"] = grad_data
            print(f"    졸업 API 응답: {len(grad_data)}개")
        else:
            print(f"    졸업 데이터 없음")

        # === 4. 개인 시간표 ===
        print(f"\n  [4/4] 개인 시간표...")
        timetable_apis = [
            "EdcRegi",
            "EdcLesn",
            "doList",
        ]
        tt_data = await _capture_apis(page, "수업/강의평가", "개인강의시간표조회", timetable_apis, wait_sec=5)

        if tt_data:
            result["timetable"] = tt_data
            print(f"    시간표 API 응답: {len(tt_data)}개")
        else:
            print(f"    시간표 데이터 없음")

        save_json(result, RAW_DIR / "ndrims.json")
        print(f"\n[ndrims] 완료")
        return result
