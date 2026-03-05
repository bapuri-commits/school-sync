"""통합 설정 모듈.

config.yaml에서 사이트별 설정을 로드하고,
기존 eclass_crawler 코드가 `from config import BASE_URL` 형태로
그대로 사용할 수 있도록 모듈-레벨 변수를 제공한다.
"""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

# --- 크레덴셜 ---
SCHOOL_USERNAME = os.getenv("SCHOOL_USERNAME", "")
SCHOOL_PASSWORD = os.getenv("SCHOOL_PASSWORD", "")

# --- 공통 ---
CURRENT_SEMESTER: str = _cfg.get("semester", "2026-1")
REQUEST_DELAY: float = _cfg.get("request_delay", 0.5)
REQUEST_TIMEOUT: float = _cfg.get("request_timeout", 30.0)
OUTPUT_DIR = Path(__file__).parent / _cfg.get("output_dir", "output")

# --- 사이트별 설정 ---
SITES: dict = _cfg.get("sites", {})

# --- eClass (기존 extractor 호환용) ---
_eclass_cfg = SITES.get("eclass", {})
BASE_URL: str = _eclass_cfg.get("base_url", "https://eclass.dongguk.edu")
GLOBAL_BOARD_IDS: set[int] = set(_eclass_cfg.get("global_board_ids", [31, 32, 33]))
MIN_DOWNLOAD_SIZE_BYTES: int = _eclass_cfg.get("min_download_size_bytes", 512)

