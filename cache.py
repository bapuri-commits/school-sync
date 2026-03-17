"""크롤링 캐시 — URL+날짜 기반 중복 수집 방지."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from config import OUTPUT_DIR

CACHE_DIR = OUTPUT_DIR / "cache"
CACHE_FILE = CACHE_DIR / "collected_posts.json"


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict):
    """원자적 쓰기로 캐시를 저장한다 (임시 파일 → rename)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    content = json.dumps(cache, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=str(CACHE_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(CACHE_FILE)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def is_new_or_updated(url: str, date: str = "") -> bool:
    """URL이 캐시에 없거나, 날짜가 변경되었으면 True."""
    cache = _load_cache()
    entry = cache.get(url)
    if not entry:
        return True
    if date and entry.get("date") != date:
        return True
    return False


def mark_collected(url: str, date: str = "", body_hash: str = ""):
    """수집 완료된 글을 캐시에 기록한다."""
    cache = _load_cache()
    cache[url] = {"date": date, "body_hash": body_hash}
    _save_cache(cache)


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class CacheBatch:
    """캐시를 배치로 읽기/쓰기하는 context manager.
    루프 안에서 매번 파일 I/O 하는 대신, 진입 시 한 번 로드하고 종료 시 한 번 저장한다.
    """

    def __enter__(self):
        self._cache = _load_cache()
        return self

    def __exit__(self, *_):
        _save_cache(self._cache)

    def is_new_or_updated(self, url: str, date: str = "") -> bool:
        entry = self._cache.get(url)
        if not entry:
            return True
        if date and entry.get("date") != date:
            return True
        return False

    def mark_collected(self, url: str, date: str = "", body_hash: str = "") -> None:
        self._cache[url] = {"date": date, "body_hash": body_hash}
