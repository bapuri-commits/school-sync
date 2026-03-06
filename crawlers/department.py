"""
학과 사이트 크롤러 — 공지사항 + 학사자료, 본문 + 첨부파일 포함.
인증 불필요 (공개 페이지).
"""

import asyncio
import json
from pathlib import Path

from browser import BrowserSession
from config import OUTPUT_DIR, SITES, REQUEST_DELAY, REQUEST_TIMEOUT

_GOTO_TIMEOUT = int(REQUEST_TIMEOUT * 1000)
from crawlers.base import BaseCrawler
from cache import is_new_or_updated, mark_collected, content_hash

RAW_DIR = OUTPUT_DIR / "raw" / "department"
DL_DIR = OUTPUT_DIR / "downloads" / "department"

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

        default_boards = [
            {"key": "notices", "path": "notice", "label": "학과공지"},
            {"key": "external_notices", "path": "notice2", "label": "특강/공모전/취업"},
            {"key": "college_data", "path": "collegedata", "label": "학사자료"},
        ]
        boards = _dept_cfg.get("boards", default_boards)

        for b in boards:
            key, path, label = b["key"], b["path"], b["label"]
            try:
                posts = await self._extract_notices(page, board_path=path, board_label=label)
                result[key] = posts
            except Exception as e:
                print(f"  [에러] {label} 추출 실패: {e}")
                result[key] = {"_error": str(e)}

        _save_json(result, RAW_DIR / "notices.json")
        for b in boards:
            key, label = b["key"], b["label"]
            count = len(result.get(key, []))
            if isinstance(result.get(key), list) and count > 0:
                body_count = sum(1 for p in result[key] if p.get("_body"))
                print(f"  [{label}] {count}개 (본문 {body_count}개)")

        print(f"\n[department] 완료")
        return result

    async def _extract_notices(self, page, board_path: str = "notice", board_label: str = "학과공지", max_pages: int = 2) -> list[dict]:
        """학과 게시판에서 글 목록 + 본문 + 첨부파일을 추출한다."""
        all_posts = []
        for page_idx in range(1, max_pages + 1):
            url = f"{BASE_URL}/article/{board_path}/list?pageIndex={page_idx}"
            await page.goto(url, wait_until="networkidle", timeout=_GOTO_TIMEOUT)

            posts = await page.evaluate("""
                () => {
                    const posts = [];
                    document.querySelectorAll('table tbody tr').forEach(tr => {
                        const cells = tr.querySelectorAll('td');
                        if (cells.length < 3) return;

                        const linkEl = tr.querySelector('a[href*="detail"]');
                        const title = linkEl ? linkEl.innerText.trim() : '';
                        if (!title) return;

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

        new_count = 0
        for post in unique:
            url = post.get("url", "")
            date = post.get("date", "")
            if url and is_new_or_updated(url, date):
                body_data = await self._extract_post_body(page, url)
                post["_body"] = body_data.get("body", "")
                post["_attachments"] = body_data.get("attachments", [])
                mark_collected(url, date, content_hash(post.get("_body", "")))
                new_count += 1
                await asyncio.sleep(REQUEST_DELAY)

        if new_count > 0:
            print(f"    본문 수집: {new_count}개 (신규/변경)")

        return unique

    async def _extract_post_body(self, page, detail_url: str) -> dict:
        """글 상세 페이지에서 본문과 첨부파일을 추출한다."""
        try:
            await page.goto(detail_url, wait_until="networkidle", timeout=_GOTO_TIMEOUT)

            data = await page.evaluate("""
                () => {
                    const result = { body: '', attachments: [] };

                    const bodyEl = document.querySelector(
                        '.board_view_content, .view_content, .board-view-content, ' +
                        '.contents .view, article, .detail-content'
                    );
                    if (bodyEl) {
                        result.body = bodyEl.innerText.trim().substring(0, 10000);
                    } else {
                        const main = document.querySelector('.contents, #contents, main');
                        if (main) result.body = main.innerText.trim().substring(0, 10000);
                    }

                    document.querySelectorAll(
                        'a[href*="download"], a[href*="file"], ' +
                        '.file-list a[href], .attach a[href], ' +
                        'a[href*="attachFile"], a[href*="pluginfile"]'
                    ).forEach(a => {
                        const href = a.href;
                        const text = a.innerText.trim();
                        if (href && !href.startsWith('javascript') && text && text.length > 1) {
                            result.attachments.push({ name: text, url: href });
                        }
                    });

                    return result;
                }
            """)
            return data
        except Exception as e:
            return {"body": "", "attachments": [], "_error": str(e)}
