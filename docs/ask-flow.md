# school_sync ask.py — 질문-답변 처리 흐름 상세 분석

## 전체 흐름 (CLI 기준: `python ask.py "이번주 과제 뭐 있어?"`)

### 1단계: 초기화 (ask.py 330~344행)

```python
def main():
    parser = argparse.ArgumentParser(description="school_sync Q&A")
    parser.add_argument("question", nargs="?", help="질문 (없으면 대화 모드)")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-search", action="store_true")
    args = parser.parse_args()

    if args.refresh:
        from normalizer import normalize
        normalize()

    client = Anthropic()
    history = []
    web_search = not args.no_search
```

- `Anthropic()` 클라이언트 생성 (환경변수 `ANTHROPIC_API_KEY` 사용)
- 대화 이력 `history = []` 초기화
- `--refresh` 시 크롤링 데이터를 다시 정규화

---

### 2단계: `_ask()` 호출 — 질문 분류 (275~278행)

```python
def _ask(client, question, history, web_search=True):
    categories = _classify_question(question)
    context = _load_context(categories, question)
```

`_classify_question("이번주 과제 뭐 있어?")` 실행:

```python
def _classify_question(question: str) -> set[str]:
    categories = set()
    for keyword, cats in QUESTION_CATEGORY_MAP.items():
        if keyword in question:
            categories.update(cats)
    # ...
    if not categories:
        categories = {"briefing", "academics", "profile", "schedule"}
    if categories & _BRIEFING_RELEVANT:
        categories.add("briefing")
    return categories
```

- `QUESTION_CATEGORY_MAP`에서 키워드 매칭: "과제" → `["academics"]`
- `academics`는 `_BRIEFING_RELEVANT`에 포함되므로 `briefing`도 추가
- 결과: `{"academics", "briefing"}`

---

### 3단계: 컨텍스트 로드 (214~260행)

```python
def _load_context(categories, question="", max_chars=30000):
    course_names = _get_course_names()

    candidates = []
    for rel_path, (label, category, priority) in DATA_FILES.items():
        if category not in categories:
            continue
        path = NORM_DIR / rel_path
        if not path.exists():
            continue
        candidates.append((priority, rel_path, label, path))

    candidates.sort(key=lambda x: x[0])  # 우선순위 낮은 순(중요한 순)
```

카테고리가 `{"academics", "briefing"}`이므로 `DATA_FILES`에서 해당하는 파일만 선택:

| 파일 | 라벨 | 우선순위 |
|---|---|---|
| `briefing.md` | 오늘의 브리핑 | 10 |
| `academics/deadlines.json` | 마감 일정 | 15 |
| `academics/assignments.json` | 과제/활동 | 18 |
| `academics/courses.json` | 수강 과목 | 20 |
| `academics/grades.json` | eclass 성적 | 30 |
| `academics/attendance.json` | 출석 기록 | 40 |

- 우선순위 낮은 순(중요한 순)으로 정렬
- `MAX_CONTEXT_CHARS`(30,000자) 초과하면 뒤쪽 잘라냄
- JSON 리스트 데이터는 `_smart_filter()`로 질문과 관련 있는 항목만 추출

---

### 4단계: 시스템 프롬프트 조립 (283행)

```python
system = _build_system_prompt(web_search_enabled=web_search) + "\n\n" + context
```

시스템 프롬프트 = 규칙/날짜 정보 + 로드된 학교 데이터.
Claude에게 "당신은 대학생의 학교 생활 데이터를 기반으로 답변하는 어시스턴트입니다"라는
역할과, 실제 정규화된 데이터가 합쳐져서 system 메시지로 들어감.

---

### 5단계: Claude API 호출 (285~324행)

```python
history.append({"role": "user", "content": question})

tools = [WEB_SEARCH_TOOL] if web_search else None
# ...
response = client.messages.create(**kwargs)

# 웹검색 도구 사용 시 재호출 루프 (최대 5라운드)
max_rounds = 5
rounds = 0
while response.stop_reason == "tool_use" and rounds < max_rounds:
    rounds += 1
    history.append({"role": "assistant", "content": response.content})
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": "웹검색이 서버에서 처리되었습니다.",
            })
    if tool_results:
        history.append({"role": "user", "content": tool_results})
    response = client.messages.create(**kwargs)

answer = _extract_text(response)
history.append({"role": "assistant", "content": response.content})
return answer
```

- `claude-sonnet-4-20250514` 모델 호출
- `web_search_20250305` 도구 활성화 시: 학교 데이터에 없는 정보는 Anthropic 서버 측에서 자동 웹검색
- `stop_reason == "tool_use"`이면 최대 5라운드까지 재호출 (클라이언트사이드 도구 대비 안전장치)
- 최종 텍스트를 추출해서 반환

---

## 웹 경로 차이 (routes/ask.py)

웹 버전은 동일한 로직이되, 세 가지가 다름:

1. **`ask_engine.py`가 브릿지**: `importlib`로 루트 `ask.py`의 함수들
   (`_build_system_prompt`, `_classify_question`, `_load_context`)을 동적 임포트
2. **SSE 스트리밍**: `client.messages.stream()`으로 토큰 단위 실시간 전송,
   프론트(`AskChat.tsx`)에서 실시간 표시
3. **세션 관리**: `user_id:session_id` 조합으로 대화 이력 관리,
   최대 50세션 / 1시간 TTL

---

## 요약 흐름도

```
질문 입력
  ↓
_classify_question() → 카테고리 분류 (키워드 매칭)
  ↓
_load_context() → 해당 카테고리의 normalized 데이터 로드
  ├─ 우선순위 정렬
  ├─ _smart_filter()로 관련 데이터만 추출
  └─ 30,000자 예산 내에서 잘라냄
  ↓
system prompt = 규칙 + 날짜 + 로드된 데이터
  ↓
Claude API 호출 (+ 웹검색 도구)
  ↓
답변 반환
```
