"""
대학 포탈 크롤러 — 학사공지, 학사일정 추출.
인증 불필요 (공개 페이지).
"""

import json
from pathlib import Path

from browser import BrowserSession
from config import OUTPUT_DIR, SITES
from crawlers.base import BaseCrawler

RAW_DIR = OUTPUT_DIR / "raw" / "portal"

_portal_cfg = SITES.get("portal", {})
BASE_URL = _portal_cfg.get("base_url", "https://www.dongguk.edu")

NOTICE_BOARDS = {
    "학사공지": "HAKSANOTICE",
    "장학공지": "JANGHAKNOTICE",
}


def _save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class PortalCrawler(BaseCrawler):
    site_name = "portal"

    def requires_auth(self) -> bool:
        return False

    async def crawl(self, session: BrowserSession, **opts) -> dict:
        page = session.page
        result = {}

        for board_label, board_code in NOTICE_BOARDS.items():
            try:
                posts = await self._extract_notices(page, board_code, board_label)
                result[board_code] = {"board_name": board_label, "posts": posts}
            except Exception as e:
                print(f"  [에러] {board_label} 추출 실패: {e}")
                result[board_code] = {"board_name": board_label, "_error": str(e)}

        try:
            schedule = await self._extract_schedule(page)
            result["academic_schedule"] = schedule
        except Exception as e:
            print(f"  [에러] 학사일정 추출 실패: {e}")
            result["academic_schedule"] = {"_error": str(e)}

        _save_json(result, RAW_DIR / "portal.json")
        total_posts = sum(
            len(v.get("posts", [])) for v in result.values() if isinstance(v, dict) and "posts" in v
        )
        schedule_count = len(result.get("academic_schedule", []))
        print(f"\n[portal] 완료 — 공지 {total_posts}개, 학사일정 {schedule_count}개")
        return result

    async def _extract_notices(self, page, board_code: str, board_label: str, max_pages: int = 2) -> list[dict]:
        """포탈 공지사항 게시판에서 글 목록을 추출한다."""
        all_posts = []
        for page_idx in range(1, max_pages + 1):
            url = f"{BASE_URL}/article/{board_code}/list?pageIndex={page_idx}"
            await page.goto(url, wait_until="networkidle")

            posts = await page.evaluate("""
                (boardCode) => {
                    const posts = [];
                    document.querySelectorAll('.board_list ul li').forEach(li => {
                        const linkEl = li.querySelector('a[onclick*="goDetail"]');
                        if (!linkEl) return;

                        const titleEl = li.querySelector('p.tit');
                        const title = titleEl ? titleEl.innerText.trim() : '';
                        if (!title) return;

                        const onclickMatch = linkEl.getAttribute('onclick').match(/goDetail\\((\\d+)\\)/);
                        const articleId = onclickMatch ? onclickMatch[1] : '';
                        const url = articleId
                            ? `https://www.dongguk.edu/article/${boardCode}/detail/${articleId}`
                            : '';

                        const cateEl = li.querySelector('.top em');
                        const category = cateEl ? cateEl.innerText.trim() : '';

                        const text = li.innerText;
                        const dateMatch = text.match(/(\\d{4}\\.\\d{2}\\.\\d{2})/);
                        const date = dateMatch ? dateMatch[1].replace(/\\./g, '-') : '';
                        const viewMatch = text.match(/조회\\s*(\\d[\\d,]*)/);
                        const views = viewMatch ? viewMatch[1].replace(/,/g, '') : '';

                        posts.push({ title, url, date, views, category });
                    });
                    return posts;
                }
            """, board_code)

            all_posts.extend(posts)
            print(f"  [{board_label}] page {page_idx}: {len(posts)}개")
            if len(posts) < 5:
                break

        seen_urls = set()
        unique = []
        for p in all_posts:
            if p["url"] and p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                unique.append(p)
            elif not p["url"]:
                unique.append(p)
        return unique

    async def _extract_schedule(self, page) -> list[dict]:
        """학사일정 페이지에서 일정 목록을 추출한다."""
        url = f"{BASE_URL}/schedule/detail?schedule_info_seq=22"
        await page.goto(url, wait_until="networkidle")

        events = await page.evaluate("""
            () => {
                const events = [];
                const items = document.querySelectorAll('.schedule-list li, .schedule_list li, .calList li, .cal-list-item');

                if (items.length > 0) {
                    items.forEach(li => {
                        const dateEl = li.querySelector('.date, .cal-date, .schedule-date, dt');
                        const titleEl = li.querySelector('.title, .cal-title, .schedule-title, dd, .txt');
                        const deptEl = li.querySelector('.dept, .sub-text, .schedule-dept');

                        events.push({
                            date_text: dateEl ? dateEl.innerText.trim() : '',
                            title: titleEl ? titleEl.innerText.trim() : '',
                            department: deptEl ? deptEl.innerText.trim() : '',
                        });
                    });
                }

                if (events.length === 0) {
                    const container = document.querySelector('.contents, #contents, .schedule-wrap, main');
                    if (container) {
                        const allText = container.innerText;
                        const lines = allText.split('\\n').map(l => l.trim()).filter(l => l);
                        let current_year = '', current_month = '';
                        for (let i = 0; i < lines.length; i++) {
                            const yearMatch = lines[i].match(/^(20\\d{2})$/);
                            const monthMatch = lines[i].match(/^(0[1-9]|1[0-2])$/);
                            if (yearMatch) { current_year = yearMatch[1]; continue; }
                            if (monthMatch) { current_month = monthMatch[1]; continue; }
                            if (current_year && current_month && lines[i].length > 2 && !lines[i].startsWith('(')) {
                                const dept_line = (i + 1 < lines.length && lines[i+1].startsWith('(')) ? lines[i+1] : '';
                                events.push({
                                    date_text: `${current_year}-${current_month}`,
                                    title: lines[i],
                                    department: dept_line.replace(/^\\(주관부서:\\s*/, '').replace(/\\)$/, ''),
                                });
                                if (dept_line) i++;
                            }
                        }
                    }
                }

                return events;
            }
        """)

        print(f"  [학사일정] {len(events)}개 항목")
        return events
