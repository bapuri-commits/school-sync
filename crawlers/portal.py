"""
대학 포탈 크롤러 — 학사공지, 학사일정 추출.
인증 불필요 (공개 페이지).
"""

from browser import BrowserSession, safe_goto
from config import OUTPUT_DIR, SITES
from crawlers.base import BaseCrawler
from utils import save_json

RAW_DIR = OUTPUT_DIR / "raw" / "portal"

_portal_cfg = SITES.get("portal", {})
BASE_URL = _portal_cfg.get("base_url", "https://www.dongguk.edu")

NOTICE_BOARDS = {
    "학사공지": "HAKSANOTICE",
    "장학공지": "JANGHAKNOTICE",
}


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

        save_json(result, RAW_DIR / "portal.json")
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
            await safe_goto(page, url)

            posts = await page.evaluate("""
                (boardCode) => {
                    const posts = [];

                    // 1차: .board_list ul li (기본 구조)
                    let items = document.querySelectorAll('.board_list ul li');
                    // 2차 fallback: 대체 게시판 셀렉터
                    if (items.length === 0) items = document.querySelectorAll('.bbs_list ul li, .notice_list li');
                    // 3차 fallback: 테이블 기반
                    if (items.length === 0) items = document.querySelectorAll('table.board tbody tr, .board_table tbody tr');

                    items.forEach(el => {
                        const linkEl = el.querySelector('a[onclick*="goDetail"], a[href*="detail"]');
                        if (!linkEl) return;

                        const titleEl = el.querySelector('p.tit, .title, .subject, td.title a, a');
                        let rawTitle = titleEl ? titleEl.innerText.trim() : '';
                        if (!rawTitle) return;

                        // p.tit의 innerText에 배지/카테고리/날짜/조회수가 혼입됨 — 실제 제목만 추출
                        let title = rawTitle;
                        const lines = rawTitle.split('\\n').map(l => l.trim()).filter(l => l);
                        if (lines.length >= 3) {
                            // 패턴: [공지|번호] / [카테고리] / [제목] / [날짜. 조회 N]
                            const cleaned = lines.filter(l =>
                                !/^공지$|^\\d+$/.test(l) &&
                                !/^\\d{4}\\.\\d{2}\\.\\d{2}/.test(l) &&
                                !/조회\\s*\\d/.test(l)
                            );
                            // 카테고리(cateEl에서 별도 추출)와 동일한 줄도 제거
                            const cateText = el.querySelector('.top em, .category, .cate');
                            const cateName = cateText ? cateText.innerText.trim() : '';
                            const finalLines = cateName
                                ? cleaned.filter(l => l !== cateName)
                                : cleaned;
                            title = finalLines.join(' ').trim() || rawTitle;
                        }

                        let articleId = '';
                        const onclick = linkEl.getAttribute('onclick') || '';
                        const onclickMatch = onclick.match(/goDetail\\((\\d+)\\)/);
                        if (onclickMatch) {
                            articleId = onclickMatch[1];
                        } else {
                            const hrefMatch = (linkEl.getAttribute('href') || '').match(/detail\\/(\\d+)/);
                            if (hrefMatch) articleId = hrefMatch[1];
                        }
                        const url = articleId
                            ? `https://www.dongguk.edu/article/${boardCode}/detail/${articleId}`
                            : '';

                        const cateEl = el.querySelector('.top em, .category, .cate');
                        const category = cateEl ? cateEl.innerText.trim() : '';

                        const text = el.innerText;
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
        seen_titles = set()
        unique = []
        for p in all_posts:
            if p["url"] and p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                unique.append(p)
            elif not p["url"]:
                dedup_key = (p.get("title", ""), p.get("date", ""))
                if dedup_key not in seen_titles:
                    seen_titles.add(dedup_key)
                    unique.append(p)
        return unique

    async def _extract_schedule(self, page) -> list[dict]:
        """학사일정 페이지에서 일정 목록을 추출한다."""
        seq = _portal_cfg.get("schedule_info_seq", 22)
        url = f"{BASE_URL}/schedule/detail?schedule_info_seq={seq}"
        await safe_goto(page, url)

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
