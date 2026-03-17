"""공통 유틸리티 — JSON I/O, Windows 인코딩 설정."""

import json
import sys
from pathlib import Path


def save_json(data, path: Path) -> None:
    """JSON 데이터를 파일에 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict | list | None:
    """JSON 파일을 읽어 반환한다. 파일이 없으면 None."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def setup_win_encoding() -> None:
    """Windows cp949 콘솔에서 한글 깨짐을 방지한다."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
