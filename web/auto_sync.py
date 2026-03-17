"""백그라운드 자동 동기화.

주기적으로 eClass 크롤링 + 정규화를 실행한다.
수동 태스크(crawl/pack)가 실행 중이면 건너뛴다.

스케줄 (UTC 기준, KST = UTC + 9):
  UTC 01-09 (매시 정각) = KST 10:00-18:00 매시 집중 동기화
  UTC 18:00             = KST 03:00 야간 배치
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

from . import tasks

logger = logging.getLogger("studyhub.auto_sync")

PYTHON = sys.executable
_KST_OFFSET = timedelta(hours=9)

_RUN_HOURS_UTC = [1, 2, 3, 4, 5, 6, 7, 8, 9, 18]

_last_auto: str | None = None
_next_auto: str | None = None
_enabled = os.getenv("AUTO_SYNC_ENABLED", "1") == "1"


def _calc_next_run_utc(now_utc: datetime) -> datetime:
    """다음 실행 시각을 UTC로 계산한다."""
    base = now_utc.replace(minute=0, second=0, microsecond=0)

    for h in _RUN_HOURS_UTC:
        candidate = base.replace(hour=h)
        if candidate > now_utc:
            return candidate

    return (base + timedelta(days=1)).replace(hour=_RUN_HOURS_UTC[0])


def _to_kst_iso(utc_dt: datetime) -> str:
    return (utc_dt + _KST_OFFSET).isoformat(timespec="minutes")


def get_auto_sync_status() -> dict:
    return {
        "enabled": _enabled,
        "schedule": "KST 10-18시 매시 + 03시",
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
    logger.info("자동 동기화 시작 (스케줄: KST 10-18시 매시 + 03시)")

    while True:
        try:
            now_utc = datetime.utcnow()
            next_run = _calc_next_run_utc(now_utc)
            wait_secs = (next_run - now_utc).total_seconds()
            _next_auto = _to_kst_iso(next_run)

            while wait_secs > 0:
                chunk = min(wait_secs, 60)
                await asyncio.sleep(chunk)
                wait_secs -= chunk
                if not _enabled:
                    break

            if not _enabled:
                continue

            if tasks.get_state().status == tasks.TaskStatus.RUNNING:
                logger.info("수동 태스크 실행 중 — 자동 동기화 건너뜀")
                continue

            logger.info("자동 동기화 실행: eclass + portal + department 크롤링")
            cmd = [PYTHON, "main.py", "--site", "eclass", "portal", "department", "--download"]
            started = await tasks.run_task("auto_sync", cmd)

            if started:
                while tasks.get_state().status == tasks.TaskStatus.RUNNING:
                    await asyncio.sleep(5)
                _last_auto = _to_kst_iso(datetime.utcnow())
                state = tasks.get_state()
                logger.info(f"자동 동기화 완료: {state.status.value} (exit={state.exit_code})")
        except asyncio.CancelledError:
            logger.info("자동 동기화 루프 취소됨")
            break
        except Exception:
            logger.exception("자동 동기화 루프 오류 — 다음 주기에 재시도")
            await asyncio.sleep(60)
