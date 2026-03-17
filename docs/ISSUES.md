# school_sync 검수 결과 — 이슈 트래커

> 2026-03-05 전체 검수, 2026-03-17 웹 감사 + 전체 리팩토링 + 심층 감사 완료.

---

## 심층 감사 (2026-03-17) — P0 즉시 수정

- [x] **useLogStream 콜백 무한루프** — `onStreamEnd` 인라인 함수가 매 렌더마다 재생성되어 `startLogStream` → `fetchTaskStatus` → 무한 리렌더. **ref 기반 콜백**으로 수정하여 안정적 참조 유지.
- [x] **ask 세션 격리 미흡** — 글로벌 `_sessions` 딕셔너리에서 `session_id`만으로 세션 관리하여 타 유저 대화 열람 가능. **`{username}:{session_id}`** 스코핑 적용.
- [x] **파일 업로드 메모리 고갈 (DoS)** — 전체 파일을 메모리에 읽은 뒤 크기 검증. **256KB 청크 단위 읽기 + 누적 크기 검증**으로 변경.
- [x] **course_filter 플래그 주입** — `--course` 뒤에 `--site` 등 임의 플래그 주입 가능. **정규식 화이트리스트 + `--` prefix 차단** 적용.
- [x] **PII(전화/이메일) LLM 전송** — `student.json`의 phone/email이 LLM 컨텍스트에 포함. **`_load_context`에서 student 데이터 로드 시 PII 필드 제거** 적용.

---

## 심층 감사 (2026-03-17) — P1 수정

- [x] **DEV_MODE 프로덕션 누출** — `DEV_MODE=1`이 프로덕션에 남으면 전체 인증 우회. **`SYOPS_SECRET_KEY`와 동시 설정 시 경고 로그** 출력.
- [x] **ask SSE 에러 정보 노출** — `str(e)`에 API 키/내부 경로 포함 가능. **일반 에러 메시지만 클라이언트 반환**, 상세는 서버 로그에 기록.
- [x] **sync 라우터 HTTP 200 에러** — 에러 상황에서 HTTP 200 반환. **HTTPException(400/409)** 으로 적절한 상태코드 사용.
- [x] **과목 서브스트링 매칭** — `course_name in d.name` 패턴으로 "AI" → "AI응용" 매칭. `routes/courses.py`와 `data_loader.py`에서 **정확 매칭(`==`)**으로 변경.
- [x] **main.py 상대경로** — `Path("output")` 하드코딩 → `OUTPUT_DIR` 사용.
- [x] **캘린더 타임존 누락** — `datetime(year, 3, 1)` naive datetime으로 Docker(UTC)에서 9시간 오차. **KST timezone-aware datetime** 적용.
- [x] **대화 히스토리 corruption** — API 호출 전에 user 메시지 추가하여 실패 시 `[user, user]` 비정상 구조. **API 성공 후에만 양쪽 메시지 추가**.
- [x] **ask_engine.py 로드 실패 시 앱 크래시** — try-except로 감싸고, 실패 시 **graceful fallback** (해당 기능만 비활성화).
- [x] **department.py dead code** — `offset = cells.length >= 5 ? 0 : 0` 양 분기 0. 삭제.
- [x] **datetime.utcnow() deprecated** — `data_loader.py`, `auto_sync.py`에서 `datetime.now(timezone.utc)` 사용으로 변경.
- [x] **Anthropic 클라이언트 매 요청 생성** — 모듈 레벨 싱글턴 `_get_client()`로 커넥션 풀 재사용.

---

## 이전 이슈 — P0 (전부 해결)

- [x] **materials.py NameError** — `total` 변수 할당 전 사용
- [x] **QUESTION_CATEGORY_MAP 키워드 부족** — 15개 → 33개
- [x] **briefing 항상 포함** — `_BRIEFING_RELEVANT` 조건 추가

## 이전 이슈 — P1 (전부 해결)

- [x] **extractor timeout 미설정** — 6개 파일에 `_GOTO_TIMEOUT` 적용
- [x] **Notice.date 형식 불일치** — `_normalize_date()` 추가
- [x] **calendar.py 응답 검증** — JSON 파싱 실패 방어
- [x] **assignments sections 순회 누락** — URL 기반 중복 제거

## 이전 이슈 — P2 (전부 해결)

- [x] **HTML 파싱 취약** — portal/department fallback 셀렉터 3단계
- [x] **"강의" 키워드 과매칭** — 2차 분류 로직
- [x] **system prompt timetable 예시** — 형식 예시 추가
- [x] **max_tokens 2048** → 4096
- [x] **TimetableEntry 모델 미사용** → Pydantic 모델 적용
- [x] **하드코딩 설정값** → config.yaml 기반

## 이전 이슈 — P3 (전부 해결)

- [x] **browser.py 컨텍스트 매니저** — `__aenter__`/`__aexit__`
- [x] **cache.py 동시 접근** — 원자적 쓰기 (tempfile→rename)
- [x] **cache.py 데드코드** — `is_file_downloaded` 제거
- [x] **GradeItem.range** → `score_range`
- [x] **NormalizedOutput syllabus** — SyllabusEntry 모델 갱신 + 통합
- [x] **--refresh 도움말** — 명확화
- [x] **syllabus 데이터 품질** — 주차 중복 제거, HTML 이스케이프 정리

## 웹 리팩토링 (전부 해결)

- [x] **ask.py sys.path.insert** → ask_engine.py 브릿지
- [x] **SSE 코드 중복** → useLogStream 훅
- [x] **auto_sync 반응 지연** — 60초 체크 + 비활성 분리
- [x] **Error Boundary** — 전체+라우트별
- [x] **tasks.py 멀티 워커** — 경고 로직
- [x] **docker-compose 리소스** — 2G/1.5CPU 제한
- [x] **data_loader.py 과목 필터** — `in` → `==` 정확 매칭
- [x] **ask.py 질문 길이/히스토리** — 2000자/20턴 제한
- [x] **auth.py mtime 캐시** — 파일 변경 시만 재로드
- [x] **gdrive 경로 검증** — `_validate_course()` 추가
- [x] **docker-compose healthcheck** — 60초 간격

## SyOps 연동 (해결)

- [x] **nginx study.conf** — SSE 버퍼링 off 포함

---

## 미해결 (P2-P3, 장기 개선)

### P2 — 계획적으로 수정

- [ ] **캐시 매번 전체 I/O (O(n²))** — `cache.py`의 `is_new_or_updated`/`mark_collected`가 매 호출마다 전체 파일 읽기/쓰기. 배치 context manager 패턴으로 변환 필요.
- [ ] **CORS allow_methods/allow_headers 과도** — `["*"]` 대신 실제 사용 메서드/헤더만 명시.
- [ ] **GDrive 토큰 비원자적 쓰기** — 토큰 갱신 시 `write_text` 직접 사용. 임시 파일 + rename으로 변경.
- [ ] **`_save_json` 헬퍼 4곳 중복** — 공통 유틸 모듈로 추출.
- [ ] **`_GOTO_TIMEOUT` 6곳 중복** — `config.py`에 `GOTO_TIMEOUT_MS` 상수 추가.
- [ ] **Windows 인코딩 우회 코드 2곳 중복** — 공통 함수로 추출.
- [ ] **data_loader 매번 디스크 I/O** — mtime 기반 캐시 도입.
- [ ] **normalizer.py 과도한 책임 (759줄)** — 변환/저장/출력 분리.
- [ ] **config.py 모듈 레벨 사이드 이펙트** — lazy loading 또는 `get_config()` 패턴.
- [ ] **ndrims_grade_history NormalizedOutput 미포함** — 모델과 실제 출력 불일치.

### P3 — 개선 권장

- [ ] **asyncio.create_task() 참조 미보관** — done_callback 패턴 사용.
- [ ] **tasks.py env=None 전체 환경변수 상속** — 최소 권한 원칙.
- [ ] **health 엔드포인트 last_crawl 노출** — 인증 필요 엔드포인트로 분리.
- [ ] **ndrims.py 미사용 변수 total_entries** — 제거.
- [ ] **browser.py dialog handler 미제거** — 이후 탐색에 영향.
- [ ] **calendar.py 미사용 import time** — 제거.
- [ ] **URL 없는 포탈 공지 중복 가능** — dedup 로직 보완.
- [ ] **크롤러 간 에러 구조 불일치** — 통일된 에러 포맷.
- [ ] **BaseCrawler.requires_auth() 미사용** — 호출하거나 제거.
- [ ] **auto_sync 시간 드리프트** — 루프마다 현재 시각 재계산.

### Future

- **SyOps JWT 인증 통합**: permissions.yaml → JWT + 서비스 권한
- **nDRIMS SSO 자동 로그인**: credential 기반 자동화
- **HTML 스냅샷 기반 단위 테스트**: extractor별 테스트
- **시간표 구조화**: 자연어 → day/start/end 파싱
- **MCP 서버 전환**: The_Agent 연동 시
