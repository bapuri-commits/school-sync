"""ask.py 모듈 브릿지 — web 패키지에서 root ask.py의 함수를 사용할 수 있게 한다."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

_log = logging.getLogger("studyhub.ask_engine")
_ASK_PATH = Path(__file__).resolve().parent.parent / "ask.py"

try:
    _spec = importlib.util.spec_from_file_location("_ask_module", _ASK_PATH)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    _build_system_prompt = _mod._build_system_prompt
    _classify_question = _mod._classify_question
    _load_context = _mod._load_context
    WEB_SEARCH_TOOL = _mod.WEB_SEARCH_TOOL
except Exception as e:
    _log.error("ask.py 로드 실패: %s — AI Q&A 기능이 비활성화됩니다", e)

    def _build_system_prompt(web_search_enabled: bool = True) -> str:
        return "AI Q&A 모듈 로드에 실패했습니다."

    def _classify_question(question: str, client=None) -> tuple:
        return set(), None

    def _load_context(categories: set[str], question: str = "", max_chars: int = 30000) -> str:
        return ""

    WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
