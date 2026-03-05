"""크롤링 캐시 — URL+날짜 기반 중복 수집 방지."""

import hashlib
import json
from pathlib import Path

from config import OUTPUT_DIR

CACHE_DIR = OUTPUT_DIR / "cache"
CACHE_FILE = CACHE_DIR / "collected_posts.json"


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


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


def is_file_downloaded(dest_dir: Path, filename: str) -> bool:
    """동일 파일명이 이미 다운로드되어 있는지 확인한다."""
    return (dest_dir / filename).exists()
