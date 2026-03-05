"""
학과 사이트 크롤러 — 학과 공지사항 추출.
인증 불필요 (공개 페이지).
"""

import json
from pathlib import Path

from browser import BrowserSession
from config import OUTPUT_DIR, SITES
from crawlers.base import BaseCrawler

RAW_DIR = OUTPUT_DIR / "raw" / "department"

_dept_cfg = SITES.get("department", {})
BASE_URL = _dept_cfg.get("base_url", "https://ai.dongguk.edu")


def _save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class DepartmentCrawler(BaseCrawler):
    site_name = "department"

    def requires_auth(self) -> bool:
        return False

    async def crawl(self, session: BrowserSession, **opts) -> dict:
        page = session.page
        result = {}

        try:
            posts = await self._extract_notices(page)
            result["notices"] = posts
        except Exception as e:
            print(f"  [에러] 학과 공지 추출 실패: {e}")
            result["notices"] = {"_error": str(e)}

        try:
            ext_posts = await self._extract_notices(page, board_path="notice2", board_label="특강/공모전/취업")
            result["external_notices"] = ext_posts
        except Exception as e:
            print(f"  [에러] 특강/공모전 공지 추출 실패: {e}")
            result["external_notices"] = {"_error": str(e)}

        _save_json(result, RAW_DIR / "notices.json")
        n1 = len(result.get("notices", []))
        n2 = len(result.get("external_notices", []))
        print(f"\n[department] 완료 — 공지 {n1}개, 특강/공모전 {n2}개")
        return result

    async def _extract_notices(self, page, board_path: str = "notice", board_label: str = "학과공지", max_pages: int = 2) -> list[dict]:
        """학과 게시판에서 글 목록을 추출한다."""
        all_posts = []
        for page_idx in range(1, max_pages + 1):
            url = f"{BASE_URL}/article/{board_path}/list?pageIndex={page_idx}"
            await page.goto(url, wait_until="networkidle")

            posts = await page.evaluate("""
                () => {
                    const posts = [];
                    // ai.dongguk.edu는 테이블 기반 게시판
                    document.querySelectorAll('table tbody tr').forEach(tr => {
                        const cells = tr.querySelectorAll('td');
                        if (cells.length < 3) return;

                        const linkEl = tr.querySelector('a[href*="detail"]');
                        const title = linkEl ? linkEl.innerText.trim() : '';
                        if (!title) return;

                        // 테이블 구조: 번호 | 제목 | 작성자 | 작성일 | 조회수 | 파일
                        posts.push({
                            title: title,
                            url: linkEl ? linkEl.href : '',
                            author: cells.length > 2 ? cells[2].innerText.trim() : '',
                            date: cells.length > 3 ? cells[3].innerText.trim() : '',
                            views: cells.length > 4 ? cells[4].innerText.trim() : '',
                        });
                    });
                    return posts;
                }
            """)

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
        return unique
