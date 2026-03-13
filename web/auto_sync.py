"""백그라운드 자동 동기화.

주기적으로 eClass 크롤링 + 정규화를 실행한다.
수동 태스크(crawl/pack)가 실행 중이면 건너뛴다.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

from . import tasks

logger = logging.getLogger("studyhub.auto_sync")

INTERVAL_HOURS = int(os.getenv("AUTO_SYNC_INTERVAL", "6"))
PYTHON = sys.executable

_last_auto: str | None = None
_next_auto: str | None = None
_enabled = os.getenv("AUTO_SYNC_ENABLED", "1") == "1"


def get_auto_sync_status() -> dict:
    return {
        "enabled": _enabled,
        "interval_hours": INTERVAL_HOURS,
        "last_auto": _last_auto,
        "next_auto": _next_auto,
    }


def set_enabled(enabled: bool) -> None:
    global _enabled
    _enabled = enabled
    logger.info(f"자동 동기화 {'활성화' if enabled else '비활성화'}")


async def auto_sync_loop():
    """메인 자동 동기화 루프. app startup에서 호출."""
    global _last_auto, _next_auto

    await asyncio.sleep(30)
    logger.info(f"자동 동기화 시작 (간격: {INTERVAL_HOURS}시간)")

    while True:
        try:
            _next_auto = (datetime.now() + timedelta(hours=INTERVAL_HOURS)).isoformat(timespec="minutes")

            await asyncio.sleep(INTERVAL_HOURS * 3600)

            if not _enabled:
                continue

            if tasks.get_state().status == tasks.TaskStatus.RUNNING:
                logger.info("수동 태스크 실행 중 — 자동 동기화 건너뜀")
                continue

            logger.info("자동 동기화 실행: eclass 크롤링 + 정규화")
            cmd = [PYTHON, "main.py", "--site", "eclass", "--download"]
            started = await tasks.run_task("auto_sync", cmd)

            if started:
                while tasks.get_state().status == tasks.TaskStatus.RUNNING:
                    await asyncio.sleep(5)
                _last_auto = datetime.now().isoformat(timespec="seconds")
                state = tasks.get_state()
                logger.info(f"자동 동기화 완료: {state.status.value} (exit={state.exit_code})")
        except asyncio.CancelledError:
            logger.info("자동 동기화 루프 취소됨")
            break
        except Exception:
            logger.exception("자동 동기화 루프 오류 — 다음 주기에 재시도")
            await asyncio.sleep(60)
