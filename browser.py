"""
브라우저 세션 매니저.
Playwright 로그인을 한 번 수행한 뒤, 여러 페이지를 탐색하며 데이터를 추출할 수 있게 한다.

eclass_crawler의 browser.py 기반이며, 멀티 사이트 로그인을 지원한다.
"""

import asyncio
import re

from playwright.async_api import async_playwright, Browser, Page
from config import (
    BASE_URL, SCHOOL_USERNAME, SCHOOL_PASSWORD,
    REQUEST_DELAY, REQUEST_TIMEOUT, SITES,
)


class BrowserSession:
    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._logged_in = False
        self.sesskey: str | None = None
        self.cookies_dict: dict[str, str] = {}

    async def start(self, headless: bool = True):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=headless)
        context = await self._browser.new_context()
        self._page = await context.new_page()
        self._page.set_default_navigation_timeout(REQUEST_TIMEOUT * 1000)
        self._page.set_default_timeout(REQUEST_TIMEOUT * 1000)
        return self

    async def _dismiss_notice_popups(self):
        """eClass 로그인 페이지의 공지 팝업(.notice_popup)을 모두 닫는다."""
        try:
            await self._page.evaluate("""
                () => {
                    document.querySelectorAll('.notice_popup.modal').forEach(popup => {
                        popup.style.display = 'none';
                        popup.classList.remove('in', 'show');
                    });
                    // backdrop도 제거
                    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = '';
                }
            """)
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  Moodle (eClass) 로그인
    # ------------------------------------------------------------------
    async def login_eclass(self, username: str = "", password: str = ""):
        username = username or SCHOOL_USERNAME
        password = password or SCHOOL_PASSWORD

        if not username or not password:
            raise RuntimeError(".env에 SCHOOL_USERNAME/SCHOOL_PASSWORD를 입력해주세요.")

        await self._page.goto(f"{BASE_URL}/login/index.php", wait_until="networkidle")

        # 공지 팝업이 로그인 버튼을 가리는 경우 모두 닫기
        await self._dismiss_notice_popups()

        await self._page.fill('input[name="username"]', username)
        await self._page.fill('input[name="password"]', password)
        await self._page.click('button[type="submit"], input[type="submit"], #loginbtn')
        await self._page.wait_for_load_state("networkidle")

        if "login" in self._page.url and "index.php" in self._page.url:
            raise RuntimeError("로그인 실패 - ID/PW를 확인해주세요.")

        self._logged_in = True

        try:
            self.sesskey = await self._page.evaluate(
                "() => typeof M !== 'undefined' && M.cfg ? M.cfg.sesskey : null"
            )
        except Exception:
            pass
        if not self.sesskey:
            content = await self._page.content()
            match = re.search(r'"sesskey"\s*:\s*"([^"]+)"', content)
            if match:
                self.sesskey = match.group(1)

        cookies = await self._page.context.cookies()
        self.cookies_dict = {c["name"]: c["value"] for c in cookies}

        print(f"[SESSION] eClass 로그인 성공: {self._page.url}")

    # ------------------------------------------------------------------
    #  SSO 로그인 (nDRIMS — 수동 로그인만 지원)
    # ------------------------------------------------------------------
    async def login_ndrims(self, username: str = "", password: str = ""):
        """nDRIMS SSO 로그인. headed 브라우저에서 수동 로그인을 기다린다.

        nDRIMS는 2단계 인증(EZGuard) 등 보안 정책으로 자동 로그인 불가.
        로컬 환경에서 headed 브라우저로만 사용 가능 (Docker 불가).
        """
        ndrims_cfg = SITES.get("ndrims", {})
        base_url = ndrims_cfg.get("base_url", "https://ndrims.dongguk.edu")

        print(f"[SESSION] nDRIMS 브라우저를 엽니다: {base_url}")
        print(f"[SESSION] 브라우저에서 SSO 로그인을 완료해주세요.")

        self._page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        await self._page.goto(base_url, wait_until="networkidle", timeout=60000)

        for _ in range(120):
            await asyncio.sleep(1)
            url = self._page.url
            if "main.clx" in url or ("main" in url and "index" not in url):
                break

        if "main.clx" in self._page.url:
            self._logged_in = True
            cookies = await self._page.context.cookies()
            self.cookies_dict = {c["name"]: c["value"] for c in cookies}
            print(f"[SESSION] nDRIMS 로그인 성공: {self._page.url}")
        else:
            print(f"[SESSION] nDRIMS 로그인 대기 중... 브라우저에서 로그인을 완료해주세요.")
            try:
                input(">>> 로그인 완료 후 Enter를 누르세요... ")
            except (EOFError, KeyboardInterrupt):
                raise RuntimeError("nDRIMS 로그인 취소됨 (Docker 환경에서는 사용 불가)")
            await asyncio.sleep(2)
            cookies = await self._page.context.cookies()
            self.cookies_dict = {c["name"]: c["value"] for c in cookies}
            self._logged_in = True
            print(f"[SESSION] nDRIMS 세션 확보: {self._page.url}")

    async def login_sso(self, site_name: str):
        if site_name == "ndrims":
            await self.login_ndrims()
            return
        site_cfg = SITES.get(site_name)
        if not site_cfg:
            raise RuntimeError(f"config.yaml에 '{site_name}' 사이트 설정이 없습니다.")
        print(f"[SESSION] SSO 로그인은 아직 미구현입니다: {site_name}")

    # ------------------------------------------------------------------
    #  레거시 호환 — 기존 eclass_crawler의 login()
    # ------------------------------------------------------------------
    async def login(self, username: str = "", password: str = ""):
        await self.login_eclass(username, password)

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("브라우저가 시작되지 않았습니다. start()를 먼저 호출하세요.")
        return self._page

    async def goto(self, url: str, delay: float = REQUEST_DELAY) -> Page:
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            await self._page.goto(url, wait_until="networkidle")
        except Exception as e:
            print(f"[SESSION] 페이지 로드 실패 ({url}): {e}")
            raise
        return self._page

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


async def create_session(headless: bool = True, site: str = "eclass") -> BrowserSession:
    """브라우저 세션을 생성하고, 필요한 사이트에 로그인한다."""
    session = BrowserSession()

    if site == "ndrims":
        if headless:
            raise RuntimeError(
                "nDRIMS는 SSO 수동 로그인이 필요합니다. "
                "Docker/서버 환경에서는 사용할 수 없습니다. "
                "로컬 환경에서 python main.py --site ndrims 로 실행해주세요."
            )
        await session.start(headless=False)
        await session.login_ndrims()
    else:
        await session.start(headless=headless)
        if site == "eclass":
            await session.login_eclass()

    return session
