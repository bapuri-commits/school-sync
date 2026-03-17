"""크롤러 공통 인터페이스."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from browser import BrowserSession


@dataclass
class CrawlError:
    """크롤러 에러 표준 포맷."""
    source: str
    section: str
    message: str

    def to_dict(self) -> dict:
        return {"_error": self.message, "_source": self.source, "_section": self.section}


class BaseCrawler(ABC):
    site_name: str

    @abstractmethod
    async def crawl(self, session: BrowserSession, **opts) -> dict:
        """크롤링 실행. 사이트별 raw dict 반환."""
        ...

    @abstractmethod
    def requires_auth(self) -> bool:
        """SSO 로그인이 필요한지 여부."""
        ...
