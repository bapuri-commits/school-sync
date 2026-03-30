"""AI Q&A 라우터 — school_sync ask.py를 SSE 스트리밍으로 래핑."""

from __future__ import annotations

import json
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import require_permission
from ..ask_engine import _build_system_prompt, _classify_question, _load_context, WEB_SEARCH_TOOL

router = APIRouter()

MAX_SESSIONS = 50
SESSION_TTL = 3600
MAX_QUESTION_LEN = 2000
MAX_HISTORY_TURNS = 20

_sessions: OrderedDict[str, dict] = OrderedDict()

_anthropic_client = None


def _get_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic()
    return _anthropic_client


class AskRequest(BaseModel):
    question: str
    web_search: bool = True
    session_id: str = "default"


def _evict_expired():
    now = time.time()
    expired = [k for k, v in _sessions.items() if now - v["ts"] > SESSION_TTL]
    for k in expired:
        del _sessions[k]
    while len(_sessions) > MAX_SESSIONS:
        _sessions.popitem(last=False)


def _get_history(session_id: str) -> list[dict]:
    _evict_expired()
    if session_id not in _sessions:
        _sessions[session_id] = {"ts": time.time(), "history": []}
    entry = _sessions[session_id]
    entry["ts"] = time.time()
    _sessions.move_to_end(session_id)
    return entry["history"]


async def _stream_response(question: str, history: list[dict], web_search: bool):
    """Anthropic API를 호출하고 SSE 형식으로 스트리밍한다."""
    import logging
    log = logging.getLogger("studyhub.ask")

    client = _get_client()

    categories, mentioned_course = _classify_question(question, client)
    context = _load_context(categories, question, mentioned_course=mentioned_course)

    if not context:
        yield f"data: {json.dumps({'type': 'error', 'text': 'normalized 데이터가 없습니다.'}, ensure_ascii=False)}\n\n"
        return

    system = _build_system_prompt(web_search_enabled=web_search) + "\n\n" + context

    tools = [WEB_SEARCH_TOOL] if web_search else None
    kwargs = dict(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        messages=history + [{"role": "user", "content": question}],
        temperature=0,
    )
    if tools:
        kwargs["tools"] = tools

    full_text = ""
    try:
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                full_text += text
                yield f"data: {json.dumps({'type': 'text', 'text': text}, ensure_ascii=False)}\n\n"

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": full_text})
    except Exception as e:
        log.exception("Ask API 호출 실패")
        yield f"data: {json.dumps({'type': 'error', 'text': 'AI 응답 생성 중 오류가 발생했습니다.'}, ensure_ascii=False)}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/ask")
async def ask(body: AskRequest, user: dict = Depends(require_permission("ask"))):
    if len(body.question) > MAX_QUESTION_LEN:
        from fastapi import HTTPException
        raise HTTPException(400, f"질문이 너무 깁니다 (최대 {MAX_QUESTION_LEN}자)")
    user_id = user.get("username", user.get("sub", "anon"))
    scoped_sid = f"{user_id}:{body.session_id}"
    history = _get_history(scoped_sid)
    if len(history) > MAX_HISTORY_TURNS * 2:
        del history[: len(history) - MAX_HISTORY_TURNS * 2]
    return StreamingResponse(
        _stream_response(body.question, history, body.web_search),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ResetRequest(BaseModel):
    session_id: str = "default"


@router.post("/ask/reset")
async def reset_session(body: ResetRequest = ResetRequest(), user: dict = Depends(require_permission("ask"))):
    user_id = user.get("username", user.get("sub", "anon"))
    scoped_sid = f"{user_id}:{body.session_id}"
    if scoped_sid in _sessions:
        del _sessions[scoped_sid]
    return {"status": "ok", "session_id": body.session_id}
