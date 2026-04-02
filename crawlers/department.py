"""
학과 사이트 크롤러 — 공지사항 + 학사자료 + 정적 페이지(교육과정/졸업요건).
인증 불필요 (공개 페이지).
"""

import asyncio
import json

from browser import BrowserSession, safe_goto
from config import OUTPUT_DIR, SITES, REQUEST_DELAY
from crawlers.base import BaseCrawler
from cache import CacheBatch, content_hash
from utils import save_json

RAW_DIR = OUTPUT_DIR / "raw" / "department"
DL_DIR = OUTPUT_DIR / "downloads" / "department"

_dept_cfg = SITES.get("department", {})
BASE_URL = _dept_cfg.get("base_url", "https://ai.dongguk.edu")

STATIC_PAGES = [
    {"key": "curriculum_2023", "url": f"{BASE_URL}/page/30427", "label": "전공교육과정(2023)", "follow_subpages": True},
    {"key": "curriculum_2026", "url": f"{BASE_URL}/page/32267", "label": "전공교육과정(2026)", "follow_subpages": True},
    {"key": "micro_degree", "url": f"{BASE_URL}/page/2836", "label": "마이크로디그리"},
    {"key": "dept_intro", "url": f"{BASE_URL}/page/31627", "label": "컴퓨터AI학부 소개"},
]


class DepartmentCrawler(BaseCrawler):
    site_name = "department"

    def requires_auth(self) -> bool:
        return False

    def _load_previous_raw(self) -> dict:
        """이전 크롤링의 raw 데이터에서 URL→body/attachments 맵을 구성한다."""
        body_map: dict[str, dict] = {}
        raw_path = RAW_DIR / "notices.json"
        if raw_path.exists():
            try:
                prev = json.loads(raw_path.read_text(encoding="utf-8"))
                for board_posts in prev.values():
                    if isinstance(board_posts, list):
                        for p in board_posts:
                            url = p.get("url", "")
                            if url and p.get("_body"):
                                body_map[url] = {
                                    "_body": p["_body"],
                                    "_attachments": p.get("_attachments", []),
                                }
            except Exception:
                pass
        return body_map

    async def crawl(self, session: BrowserSession, **opts) -> dict:
        page = session.page
        result = {}

        prev_body_map = self._load_previous_raw()

        # --- 게시판 크롤링 ---
        default_boards = [
            {"key": "notices", "path": "notice", "label": "학과공지"},
            {"key": "external_notices", "path": "notice2", "label": "특강/공모전/취업"},
            {"key": "college_data", "path": "collegedata", "label": "학사자료"},
        ]
        boards = _dept_cfg.get("boards", default_boards)

        for b in boards:
            key, path, label = b["key"], b["path"], b["label"]
            try:
                posts = await self._extract_notices(page, board_path=path, board_label=label,
                                                    prev_body_map=prev_body_map)
                result[key] = posts
            except Exception as e:
                print(f"  [에러] {label} 추출 실패: {e}")
                result[key] = {"_error": str(e)}

        save_json(result, RAW_DIR / "notices.json")
        for b in boards:
            key, label = b["key"], b["label"]
            count = len(result.get(key, []))
            if isinstance(result.get(key), list) and count > 0:
                body_count = sum(1 for p in result[key] if p.get("_body"))
                print(f"  [{label}] {count}개 (본문 {body_count}개)")

        # --- 정적 페이지 크롤링 ---
        pages_result = {}
        for sp in STATIC_PAGES:
            try:
                page_data = await self._scrape_static_page(page, sp["url"], sp["label"])

                if sp.get("follow_subpages"):
                    subpages = await self._discover_subpages(page, sp["url"])
                    for sub_url, sub_label in subpages:
                        sub_data = await self._scrape_static_page(page, sub_url, sub_label)
                        page_data["tabs"].extend(sub_data.get("tabs", []))
                        for t in sub_data.get("tabs", []):
                            t["name"] = f"{sub_label} > {t['name']}" if t["name"] != "전체" else sub_label

                pages_result[sp["key"]] = page_data
                tab_count = len(page_data.get("tabs", []))
                table_count = sum(len(t.get("tables", [])) for t in page_data.get("tabs", []))
                print(f"  [{sp['label']}] 서브페이지 {tab_count}개, 테이블 {table_count}개")
            except Exception as e:
                print(f"  [에러] {sp['label']} 추출 실패: {e}")
                pages_result[sp["key"]] = {"_error": str(e)}

        save_json(pages_result, RAW_DIR / "pages.json")

        print(f"\n[department] 완료")
        return result

    async def _discover_subpages(self, page, parent_url: str) -> list[tuple[str, str]]:
        """depth3 네비게이션에서 현재 페이지의 하위 페이지 URL을 수집한다."""
        await safe_goto(page, parent_url)
        subpages = await page.evaluate("""(parentUrl) => {
            const results = [];
            const links = document.querySelectorAll('.depth3 a');
            links.forEach(a => {
                const href = a.href || '';
                const text = a.innerText.trim();
                if (href && text && href !== parentUrl && !href.endsWith('#') && href.includes('/page/')) {
                    results.push([href, text]);
                }
            });
            return results;
        }""", parent_url)
        return [(url, label) for url, label in subpages]

    async def _scrape_static_page(self, page, url: str, label: str) -> dict:
        """정적 페이지에서 탭별 텍스트 + 테이블을 추출한다.

        동국대 학과 사이트의 두 가지 탭 구조를 처리:
        1. .menu_tabs2 li + .tab_contents (jQuery show/hide) — 전공별 교육과정
        2. 탭 없음 — 전체 본문을 하나의 탭으로
        """
        await safe_goto(page, url)

        data = await page.evaluate(r"""() => {
            const result = { title: document.title, tabs: [] };

            function extractTables(el) {
                const tables = [];
                el.querySelectorAll('table').forEach(t => {
                    const rows = [];
                    t.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('th, td').forEach(td => {
                            cells.push({
                                text: td.innerText.trim().replace(/\n/g, ' '),
                                colspan: parseInt(td.getAttribute('colspan') || '1'),
                                rowspan: parseInt(td.getAttribute('rowspan') || '1'),
                                isHeader: td.tagName === 'TH',
                            });
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    if (rows.length > 0) tables.push(rows);
                });
                return tables;
            }

            // 패턴 1: .menu_tabs2 + .tab_contents (숨겨진 탭 포함, 전공별)
            const menuTabs2 = document.querySelectorAll('.menu_tabs2 li a, .menu_tabs.menu_tabs2 li a');
            const tabContents = document.querySelectorAll('.tab_contents');

            if (menuTabs2.length > 0 && tabContents.length > 0) {
                menuTabs2.forEach((link, i) => {
                    const tabName = link.innerText.trim();
                    if (i < tabContents.length) {
                        const el = tabContents[i];
                        result.tabs.push({
                            name: tabName,
                            text: el.innerText.trim(),
                            tables: extractTables(el),
                        });
                    }
                });
            }

            // 패턴 2: 탭이 없거나 tab_contents 외 본문이 있으면 전체를 추가
            if (result.tabs.length === 0) {
                const main = document.querySelector('.contents, #contents, .sub_content, article, main') || document.body;
                result.tabs.push({
                    name: '전체',
                    text: main.innerText.trim(),
                    tables: extractTables(main),
                });
            }

            return result;
        }""")

        return data

    async def _extract_notices(self, page, board_path: str = "notice", board_label: str = "학과공지",
                               max_pages: int = 2, prev_body_map: dict | None = None) -> list[dict]:
        """학과 게시판에서 글 목록 + 본문 + 첨부파일을 추출한다."""
        all_posts = []
        for page_idx in range(1, max_pages + 1):
            url = f"{BASE_URL}/article/{board_path}/list?pageIndex={page_idx}"
            await safe_goto(page, url)

            posts = await page.evaluate("""
                () => {
                    const posts = [];

                    // 1차: 테이블 기반
                    let rows = document.querySelectorAll('table tbody tr');
                    // 2차 fallback: 대체 테이블 구조
                    if (rows.length === 0) rows = document.querySelectorAll('.board_table tbody tr, .bbs_list tbody tr');
                    // 3차 fallback: 리스트 기반
                    if (rows.length === 0) rows = document.querySelectorAll('.board_list ul li, .notice_list li');

                    rows.forEach(el => {
                        const cells = el.querySelectorAll('td');
                        const linkEl = el.querySelector('a[href*="detail"], a[href*="view"]');
                        const title = linkEl ? linkEl.innerText.trim() : '';
                        if (!title) return;

                        let author = '', date = '', views = '';
                        if (cells.length >= 3) {
                            author = cells.length > 2 ? cells[2].innerText.trim() : '';
                            date = cells.length > 3 ? cells[3].innerText.trim() : '';
                            views = cells.length > 4 ? cells[4].innerText.trim() : '';
                        } else {
                            // 리스트: 텍스트에서 날짜/조회수 추출
                            const text = el.innerText;
                            const dateMatch = text.match(/(\\d{4}[.\\-]\\d{2}[.\\-]\\d{2})/);
                            date = dateMatch ? dateMatch[1] : '';
                            const viewMatch = text.match(/조회\\s*(\\d[\\d,]*)/);
                            views = viewMatch ? viewMatch[1].replace(/,/g, '') : '';
                        }

                        posts.push({
                            title: title,
                            url: linkEl ? linkEl.href : '',
                            author: author,
                            date: date,
                            views: views,
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
        restored_count = 0
        prev = prev_body_map or {}
        with CacheBatch() as cache_batch:
            for post in unique:
                url = post.get("url", "")
                date = post.get("date", "")
                if url and cache_batch.is_new_or_updated(url, date):
                    body_data = await self._extract_post_body(page, url)
                    post["_body"] = body_data.get("body", "")
                    post["_attachments"] = body_data.get("attachments", [])
                    cache_batch.mark_collected(url, date, content_hash(post.get("_body", "")))
                    new_count += 1
                elif url in prev:
                    post["_body"] = prev[url]["_body"]
                    post["_attachments"] = prev[url]["_attachments"]
                    restored_count += 1
                await asyncio.sleep(REQUEST_DELAY)

        if new_count > 0:
            print(f"    본문 수집: {new_count}개 (신규/변경)")
        if restored_count > 0:
            print(f"    본문 복원: {restored_count}개 (캐시 히트, 이전 데이터)")

        return unique

    async def _extract_post_body(self, page, detail_url: str) -> dict:
        """글 상세 페이지에서 본문과 첨부파일을 추출한다."""
        try:
            await safe_goto(page, detail_url)

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
