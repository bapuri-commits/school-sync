"""통합 설정 모듈.

config.yaml에서 사이트별 설정을 로드하고,
기존 eclass_crawler 코드가 `from config import BASE_URL` 형태로
그대로 사용할 수 있도록 모듈-레벨 변수를 제공한다.

초기화는 _ensure_loaded()로 지연되며, 모듈 레벨 변수 접근 시 자동 로드된다.
테스트에서 config를 모킹하려면 _loaded를 False로 설정하고 변수를 덮어쓰면 된다.
"""

import os
from pathlib import Path

_loaded = False
_cfg: dict = {}

SCHOOL_USERNAME: str = ""
SCHOOL_PASSWORD: str = ""
CURRENT_SEMESTER: str = "2026-1"
REQUEST_DELAY: float = 0.5
REQUEST_TIMEOUT: float = 30.0
OUTPUT_DIR: Path = Path(__file__).parent / "output"
SITES: dict = {}
BASE_URL: str = "https://eclass.dongguk.edu"
GLOBAL_BOARD_IDS: set[int] = {31, 32, 33}
MIN_DOWNLOAD_SIZE_BYTES: int = 512
GOTO_TIMEOUT_MS: int = 30000


def _ensure_loaded() -> None:
    global _loaded, _cfg
    global SCHOOL_USERNAME, SCHOOL_PASSWORD
    global CURRENT_SEMESTER, REQUEST_DELAY, REQUEST_TIMEOUT, OUTPUT_DIR
    global SITES, BASE_URL, GLOBAL_BOARD_IDS, MIN_DOWNLOAD_SIZE_BYTES, GOTO_TIMEOUT_MS

    if _loaded:
        return
    _loaded = True

    import yaml
    from dotenv import load_dotenv

    load_dotenv()

    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            _cfg = yaml.safe_load(f) or {}

    SCHOOL_USERNAME = os.getenv("SCHOOL_USERNAME", "")
    SCHOOL_PASSWORD = os.getenv("SCHOOL_PASSWORD", "")

    CURRENT_SEMESTER = _cfg.get("semester", "2026-1")
    REQUEST_DELAY = _cfg.get("request_delay", 0.5)
    REQUEST_TIMEOUT = _cfg.get("request_timeout", 30.0)
    OUTPUT_DIR = Path(__file__).parent / _cfg.get("output_dir", "output")

    SITES = _cfg.get("sites", {})

    _eclass_cfg = SITES.get("eclass", {})
    BASE_URL = _eclass_cfg.get("base_url", "https://eclass.dongguk.edu")
    GLOBAL_BOARD_IDS = set(_eclass_cfg.get("global_board_ids", [31, 32, 33]))
    MIN_DOWNLOAD_SIZE_BYTES = _eclass_cfg.get("min_download_size_bytes", 512)
    GOTO_TIMEOUT_MS = int(REQUEST_TIMEOUT * 1000)


_ensure_loaded()

