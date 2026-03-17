"""백그라운드 태스크 매니저.

크롤링/패키징 같은 장시간 작업을 subprocess로 실행하고
상태와 로그를 관리한다. 동시 실행 1개 제한.

NOTE: 모듈 글로벌 _state를 사용하므로 uvicorn 멀티 워커(--workers > 1)에서는
태스크 상태가 워커 간 공유되지 않아 중복 실행이 발생할 수 있다.
현재는 단일 워커로 운영하며, 멀티 워커 전환 시 Redis 등 외부 상태 저장소가 필요하다.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("tasks")

_WORKER_COUNT = int(os.getenv("WEB_CONCURRENCY", "1"))
if _WORKER_COUNT > 1:
    log.warning(
        "멀티 워커(%d) 감지: 태스크 상태가 워커 간 공유되지 않습니다. "
        "태스크 중복 실행 가능성이 있습니다.",
        _WORKER_COUNT,
    )


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskState:
    status: TaskStatus = TaskStatus.IDLE
    task_type: str = ""
    started_at: str = ""
    finished_at: str = ""
    command: list[str] = field(default_factory=list)
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    exit_code: int | None = None
    _process: asyncio.subprocess.Process | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "task_type": self.task_type,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "command": self.command,
            "exit_code": self.exit_code,
            "log_lines": len(self.logs),
        }


_state = TaskState()
_bg_task: asyncio.Task | None = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_state() -> TaskState:
    return _state


def get_logs(offset: int = 0) -> list[str]:
    logs = list(_state.logs)
    return logs[offset:]


async def _read_stream(stream: asyncio.StreamReader, state: TaskState):
    """subprocess stdout/stderr를 한 줄씩 읽어서 로그에 추가한다."""
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")
        state.logs.append(decoded)


async def run_task(task_type: str, cmd: list[str], cwd: str | Path | None = None) -> bool:
    """백그라운드 태스크를 실행한다. 이미 실행 중이면 False 반환."""
    if _state.status == TaskStatus.RUNNING:
        return False

    _state.status = TaskStatus.RUNNING
    _state.task_type = task_type
    _state.started_at = datetime.now().isoformat(timespec="seconds")
    _state.finished_at = ""
    _state.command = cmd
    _state.logs.clear()
    _state.exit_code = None

    _state.logs.append(f"[StudyHub] 태스크 시작: {task_type}")
    _state.logs.append(f"[StudyHub] 명령: {' '.join(cmd)}")
    _state.logs.append("")

    async def _run():
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(cwd or PROJECT_ROOT),
                env=None,
            )
            _state._process = process

            if process.stdout:
                await _read_stream(process.stdout, _state)

            await process.wait()
            _state.exit_code = process.returncode
            _state.status = TaskStatus.COMPLETED if process.returncode == 0 else TaskStatus.FAILED
        except Exception as e:
            _state.logs.append(f"[StudyHub] 오류: {e}")
            _state.status = TaskStatus.FAILED
            _state.exit_code = -1
        finally:
            _state.finished_at = datetime.now().isoformat(timespec="seconds")
            _state._process = None
            _state.logs.append("")
            _state.logs.append(f"[StudyHub] 태스크 종료: {_state.status.value} (exit={_state.exit_code})")

    global _bg_task
    _bg_task = asyncio.create_task(_run())
    _bg_task.add_done_callback(lambda t: t.result() if not t.cancelled() and not t.exception() else None)
    return True


async def run_chained_tasks(
    task_type: str,
    steps: list[dict],
    on_complete: Callable[[], None] | None = None,
) -> bool:
    """여러 subprocess를 순차 실행한다. 중간 실패 시 중단."""
    if _state.status == TaskStatus.RUNNING:
        return False

    _state.status = TaskStatus.RUNNING
    _state.task_type = task_type
    _state.started_at = datetime.now().isoformat(timespec="seconds")
    _state.finished_at = ""
    _state.command = []
    _state.logs.clear()
    _state.exit_code = None

    _state.logs.append(f"[StudyHub] 태스크 시작: {task_type} ({len(steps)}단계)")
    _state.logs.append("")

    async def _run():
        try:
            for i, step in enumerate(steps, 1):
                cmd = step["cmd"]
                cwd = step.get("cwd", PROJECT_ROOT)
                label = step.get("label", f"단계 {i}")

                _state.logs.append(f"[StudyHub] [{i}/{len(steps)}] {label}")
                _state.logs.append(f"[StudyHub] 명령: {' '.join(cmd)}")
                _state.command = cmd

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(cwd),
                    env=None,
                )
                _state._process = process
                if process.stdout:
                    await _read_stream(process.stdout, _state)
                await process.wait()
                _state._process = None

                if process.returncode != 0:
                    _state.exit_code = process.returncode
                    _state.status = TaskStatus.FAILED
                    _state.logs.append(f"[StudyHub] {label} 실패 (exit={process.returncode})")
                    return

                _state.logs.append(f"[StudyHub] {label} 완료")
                _state.logs.append("")

            _state.exit_code = 0
            _state.status = TaskStatus.COMPLETED

            if on_complete:
                try:
                    _state.logs.append("[StudyHub] 후처리 실행 중...")
                    await asyncio.to_thread(on_complete)
                    _state.logs.append("[StudyHub] 후처리 완료")
                except Exception as e:
                    log.warning("on_complete 콜백 실패: %s", e)
                    _state.logs.append(f"[StudyHub] 후처리 실패 (무시): {e}")
        except Exception as e:
            _state.logs.append(f"[StudyHub] 오류: {e}")
            _state.status = TaskStatus.FAILED
            _state.exit_code = -1
        finally:
            _state.finished_at = datetime.now().isoformat(timespec="seconds")
            _state._process = None
            _state.logs.append("")
            _state.logs.append(f"[StudyHub] 태스크 종료: {_state.status.value} (exit={_state.exit_code})")

    global _bg_task
    _bg_task = asyncio.create_task(_run())
    _bg_task.add_done_callback(lambda t: t.result() if not t.cancelled() and not t.exception() else None)
    return True
