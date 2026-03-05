"""
nDRIMS 구조 탐색 v5 — confirm 팝업 자동 처리 + 서브메뉴 진입.

1. SSO 로그인 (수동)
2. confirm 팝업 자동 "확인"
3. 폴더 메뉴 클릭 → 서브메뉴 목록 수집 → 핵심 서브메뉴 클릭 → API/DOM 캡처
"""

import asyncio
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from playwright.async_api import async_playwright

NDRIMS_URL = "https://ndrims.dongguk.edu"
OUTPUT_PATH = Path(__file__).parent / "output" / "explore" / "ndrims_v5.json"

TARGETS = {
    "학적/확인서": ["학적부열람", "신상정보수정", "학적정보", "학적사항"],
    "성적": ["성적조회", "전체성적", "학기성적", "성적확인", "성적열람"],
    "수업/강의평가": ["시간표", "수업시간표", "강의시간표", "수강내역", "수강현황"],
    "수강신청": ["수강신청내역", "수강현황", "수강목록", "수강조회"],
}


async def click_cl_text(page, label: str) -> bool:
    """CLX .cl-text 요소를 JavaScript로 직접 클릭한다."""
    return await page.evaluate("""
        (label) => {
            const elements = document.querySelectorAll('.cl-text');
            for (const el of elements) {
                if (el.innerText.trim() === label) {
                    const target = el.closest('.cl-menu-item') || el.closest('.cl-folder') || el.parentElement || el;
                    target.click();
                    return true;
                }
            }
            return false;
        }
    """, label)


async def get_visible_cl_texts(page) -> list[str]:
    return await page.evaluate("""
        () => {
            const items = [];
            document.querySelectorAll('.cl-text').forEach(el => {
                if (el.offsetParent !== null && el.innerText.trim()) {
                    items.push(el.innerText.trim());
                }
            });
            return items;
        }
    """)


async def capture_page_data(page) -> dict:
    tables = await page.evaluate("""
        () => {
            const tables = [];
            document.querySelectorAll('table').forEach((table, idx) => {
                const headers = [];
                table.querySelectorAll('thead th, tr:first-child th').forEach(th => {
                    headers.push(th.innerText.trim().substring(0, 50));
                });
                const rows = [];
                const trs = table.querySelectorAll('tbody tr');
                const target = trs.length > 0 ? trs : table.querySelectorAll('tr');
                target.forEach((tr, i) => {
                    if (i >= 10) return;
                    const cells = [];
                    tr.querySelectorAll('td, th').forEach(td => {
                        cells.push(td.innerText.trim().substring(0, 100));
                    });
                    if (cells.length > 0) rows.push(cells);
                });
                if (headers.length > 0 || rows.length > 0)
                    tables.push({ headers, rows });
            });
            return tables;
        }
    """)

    text = await page.evaluate("""
        () => {
            const main = document.querySelector('#contents, .content, main, body');
            return main ? main.innerText.substring(0, 5000) : '';
        }
    """)

    return {"url": page.url, "tables": tables, "text": text}


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # confirm/alert 팝업 자동 수락
        page.on("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))

        print("=" * 60)
        print("  nDRIMS 구조 탐색기 v5")
        print("=" * 60)
        print(f"\n1. 브라우저에서 SSO 로그인하세요.")
        print(f"2. 팝업이 뜨면 자동으로 '확인'됩니다.")
        print(f"3. 로그인 완료 후 Enter를 누르세요.\n")

        await page.goto(NDRIMS_URL, wait_until="networkidle", timeout=60000)
        input(">>> 로그인 완료 후 Enter... ")
        await asyncio.sleep(3)

        results = {"main_url": page.url}

        for folder_name, sub_keywords in TARGETS.items():
            print(f"\n{'='*50}")
            print(f"  [{folder_name}]")
            print(f"{'='*50}")

            captured_reqs = []
            captured_resps = []

            async def on_req(req):
                url = req.url
                if "ndrims" in url and not any(x in url.split("?")[0] for x in [".js", ".css", ".png", ".jpg", ".gif", ".ico", ".woff", ".clx", ".svg", ".eot", ".ttf"]):
                    captured_reqs.append({"url": url, "method": req.method, "post_data": (req.post_data or "")[:1000]})

            async def on_resp(resp):
                url = resp.url
                if "ndrims" in url and not any(x in url.split("?")[0] for x in [".js", ".css", ".png", ".jpg", ".gif", ".ico", ".woff", ".clx", ".svg", ".eot", ".ttf"]):
                    body = ""
                    try:
                        ct = resp.headers.get("content-type", "")
                        if any(t in ct for t in ["json", "xml", "text"]):
                            body = await resp.text()
                    except Exception:
                        pass
                    captured_resps.append({"url": url, "status": resp.status, "body": body[:3000]})

            # 1) 폴더 클릭
            clicked = await click_cl_text(page, folder_name)
            print(f"  폴더 클릭: {clicked}")
            await asyncio.sleep(2)

            if not clicked:
                results[folder_name] = {"error": "폴더 못 찾음"}
                continue

            # 2) 서브메뉴 목록 확인
            visible_after = await get_visible_cl_texts(page)
            print(f"  visible 메뉴 ({len(visible_after)}개)")

            # 3) 서브메뉴 중 키워드 매칭 항목 찾기
            matched_sub = None
            for kw in sub_keywords:
                for item in visible_after:
                    if kw in item:
                        matched_sub = item
                        break
                if matched_sub:
                    break

            # 매칭 없으면 새로 나타난 항목 중 첫 번째 시도
            if not matched_sub:
                before_set = set(TARGETS.keys()) | {"대표-학사행정", "대표-행정정보", "대표-산단행정",
                    "전체메뉴", "마이메뉴", "KOR", "확대/축소", "공지사항", "공지사항조회", "메뉴명을 입력하세요."}
                new_items = [x for x in visible_after if x and len(x) > 1 and x not in before_set
                             and not x.startswith("【") and not x.startswith("[") and x not in TARGETS]
                if new_items:
                    matched_sub = new_items[0]
                    print(f"  키워드 매칭 없음, 새 항목 시도: {new_items[:5]}")

            results[folder_name] = {"sub_menus": visible_after, "matched": matched_sub}

            if matched_sub:
                print(f"  서브메뉴 클릭: [{matched_sub}]")

                page.on("request", on_req)
                page.on("response", on_resp)

                clicked_sub = await click_cl_text(page, matched_sub)
                print(f"  클릭 결과: {clicked_sub}")
                await asyncio.sleep(4)

                data = await capture_page_data(page)
                data["api_requests"] = captured_reqs
                data["api_responses"] = captured_resps
                results[folder_name]["page_data"] = data

                print(f"  API 요청: {len(captured_reqs)}개")
                for r in captured_reqs:
                    print(f"    {r['method']} {r['url'][:100]}")
                print(f"  테이블: {len(data['tables'])}개")
                for t in data["tables"]:
                    if t.get("headers"):
                        print(f"    headers: {t['headers']}")
                    elif t.get("rows"):
                        print(f"    첫 행: {t['rows'][0][:5]}")

                page.remove_listener("request", on_req)
                page.remove_listener("response", on_resp)
            else:
                print(f"  서브메뉴를 찾지 못함")

        # 저장
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n{'='*60}")
        print(f"  결과: {OUTPUT_PATH}")
        print(f"{'='*60}")

        input("\n>>> Enter로 종료... ")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
