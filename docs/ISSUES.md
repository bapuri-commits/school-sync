# school_sync 검수 결과 — 이슈 트래커

> 2026-03-05 전체 검수 후 작성. 해결된 항목은 체크 표시.

---

## 즉시 수정 완료 (P0)

- [x] **materials.py NameError** — `total` 변수가 할당 전에 사용되어 다운로드 기능 크래시. `total = len(results)`를 `success` 계산 전으로 이동, 미사용 `skipped` 제거.
- [x] **QUESTION_CATEGORY_MAP 키워드 부족** — "캘린더", "퀴즈", "시험", "휴강", "보강", "공모전", "특강", "실습", "레포트", "종강", "방학" 등 빈번한 질문 유형 추가. 15개 → 33개.
- [x] **briefing 항상 포함** — 모든 질문에 briefing.md가 컨텍스트에 포함되어 토큰 낭비. syllabus/profile만 물어볼 때는 제외하도록 `_BRIEFING_RELEVANT` 조건 추가.

---

## P1: 높은 우선순위 — 전부 해결

- [x] **1. extractor에 timeout 미설정** — 6개 파일(scanner, syllabus, notices, materials, portal, department)의 모든 `page.goto()`에 `timeout=_GOTO_TIMEOUT`(30초) 추가. `config.REQUEST_TIMEOUT` 기반.
- [x] **2. Notice.date 형식 불일치** — `_normalize_date()` 함수 추가. `YYYY.MM.DD`, `YY.MM.DD`, `YYYY/MM/DD` 등을 모두 `YYYY-MM-DD` ISO로 변환. eclass/portal/department 3곳 Notice 생성에 적용.
- [x] **3. calendar.py 응답 검증 부족** — JSON 파싱 실패 시 빈 리스트 반환, 비정상 응답 형식/API 에러 시 경고 로그 출력 후 빈 리스트 반환.
- [x] **4. assignments sections 순회 누락** — `normalize_assignments()`에서 `activities_data.get("sections", [])` 내부 활동도 순회. URL 기반 중복 제거 포함.

---

## P2: 중간 우선순위 — 일부 해결

- [ ] **5. HTML 파싱 취약 — portal/department** — `.board_list ul li`, `cells[2]` 등 특정 구조 종속. fallback 셀렉터 추가 필요.
- [ ] **6. "강의" 키워드 과매칭** — `syllabus + schedule` 둘 다 로드됨. 2차 분류 로직 도입 필요.
- [x] **7. system prompt에 timetable 형식 예시 없음** — schedule 필드의 자연어 형식(`"월 5교시(13:00) ~ 6.5교시(15:00)"`) 예시와 요일 필터 설명 추가.
- [x] **8. max_tokens 2048 제한** — `max_tokens=4096`으로 증가.
- [ ] **9. TimetableEntry 모델 미사용** — Pydantic 모델 있으나 실제로는 dict 리스트 사용. 스키마 정리 필요.
- [x] **10. 하드코딩된 설정값** — portal `schedule_info_seq`, department 게시판 목록을 `config.yaml`로 이전. 코드에서 config 기반 참조로 변경.

---

## P3: 낮은 우선순위 — 미착수

- [ ] **11. browser.py 컨텍스트 매니저 미구현** — `__aenter__`/`__aexit__` 구현 필요.
- [ ] **12. cache.py 동시 접근 문제** — 잠금 없음. 단일 실행이라 실질 영향 없음.
- [ ] **13. cache.py `is_file_downloaded` 데드 코드** — 제거 또는 활용.
- [ ] **14. GradeItem.range 필드명** — Python 내장 `range`와 이름 충돌 가능. `score_range` 등으로 변경.
- [ ] **15. NormalizedOutput에 syllabus 미포함** — 별도 저장이라 현행 유지 가능.
- [ ] **16. --refresh 의미 혼동** — help 텍스트 보완.
- [ ] **17. syllabus 데이터 품질** — 1주차 topic 중복, overview 이스케이프 잔여.

---

## 추가 작업 완료 (v1.1)

- [x] **ask.py 웹검색 연동** — Anthropic 빌트인 `web_search_20250305` 도구 추가. 로컬 데이터 부족 시 자동 웹검색. `--no-search` 옵션.
- [x] **토큰 예산 관리** — `MAX_CONTEXT_CHARS=30,000` 제한. 파일별 우선순위(5~50)로 정렬하여 중요 데이터 우선 로드.
- [x] **스마트 필터링** — notices(과목별/최근 7일), attendance(결석/지각/조퇴/유고결석, 빈 결과 시 전체 폴백), grades(과목별), academic_schedule(향후 30일).
- [x] **system prompt 하이브리드 모드** — 로컬 데이터 우선 + 웹검색 보완. 출처 구분(`[출처: 시간표]` vs `[출처: 웹검색]`).
- [x] **미사용 import 제거** — ask.py에서 `re`, `Path` 제거.

---

## 장기 개선 (Future)

- **nDRIMS SSO 자동 로그인**: 현재 수동 로그인 필수. credential 기반 자동화 또는 세션 재활용
- **HTML 스냅샷 기반 단위 테스트**: extractor별 테스트 케이스 추가
- **시간표 구조화**: 자연어 → `day_of_week/start_time/end_time` 파싱
- **공지 본문 크롤링**: portal 공지도 본문 수집
- **MCP 서버 전환**: The_Agent 연동 시
- **ask.py 2차 분류 로직**: 키워드 조합 기반 정밀 분류로 토큰 최적화
- **web_search_20260209 업그레이드**: 모델 업그레이드 시 dynamic filtering 적용으로 토큰 절감
