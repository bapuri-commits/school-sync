# school_sync 다음 세션 작업 컨텍스트

## 이전 세션에서 발견된 미완 항목

### 1. syllabus(강의계획서) 정규화 누락 — 높은 우선순위

**현상**: eclass에서 과목별 강의계획서를 크롤링하여 `output/raw/eclass/courses/{과목}.json`의 `syllabus` 필드에 저장하고 있으나, normalized 출력에는 포함되지 않음. ask.py(LLM Q&A)가 normalized 데이터만 참조하므로 "교재 알려줘" 같은 질문에 답변 불가.

**raw 데이터 예시** (`output/raw/eclass/courses/객체지향설계와패턴.json`):
```json
"syllabus": {
  "교과목명": "객체지향설계와패턴",
  "이수구분": "전공과목",
  "수업방식": "대면",
  "강의실 / 수업시간": "4105(신공학관...)",
  "이름": "이호정",
  "e-mail": "spekum@nate.com",
  "강의개요": "...",
  "강의목표": "...",
  "주교재": "(UML로 배우는)시스템 분석 설계",
  "부교재": "성공과 실패를 결정하는 1%의 객체 지향 원리",
  "1주차": "소개...",
  ...
  "15주차": "기말시험"
}
```

**해야 할 것**:
1. `normalizer.py`에 `_normalize_syllabus()` 함수 추가 — raw의 각 과목 syllabus를 정규화
2. `output/normalized/academics/syllabus.json`으로 저장 (과목별 강의계획서 배열)
3. `ask.py`의 `DATA_FILES`에 `"academics/syllabus.json"` 추가
4. `QUESTION_CATEGORY_MAP`에 "교재", "강의계획", "교수", "수업계획" 등 키워드 추가

### 2. 교재 수집 불완전 — 중간 우선순위

**현상**: eclass 강의계획서의 교재가 `주교재`/`부교재` 2개만 파싱됨. 실제 eclass 페이지에 6권이 있는 경우에도 2권만 가져옴.

**원인**: `crawlers/eclass/extractors/syllabus.py`의 generic 테이블 파서가 key-value 구조만 잡고, 교재 목록이 별도 영역(리스트 형태)으로 되어있으면 놓침.

**해야 할 것**:
1. eclass 강의계획서 페이지의 실제 HTML 구조를 확인 (explore 스크립트 또는 page.evaluate로 DOM 분석)
2. `syllabus.py`의 `extract_syllabus()` 함수에 교재 목록 전용 파서 추가
3. 교재가 테이블이 아닌 리스트(`<ul><li>`)나 별도 섹션에 있을 수 있음

**참고 파일**: `crawlers/eclass/extractors/syllabus.py` (53줄, 간단한 구조)

### 3. 기타 이전 세션에서 알려진 제한사항 (참고용)

- nDRIMS 프로필이 때때로 추출 실패 (CLX 렌더링 타이밍 문제, `_wait_for_clx` 추가했으나 완전하지 않음)
- eclass 캘린더 학기 필터링 적용했으나, 학기 초에는 과제가 없어서 빈 결과 (정상)
- 시간표 schedule 필드가 자연어 ("월 5교시(13:00) ~ 6.5교시(15:00)") — 구조화 미완
- 공지 본문은 eclass/department에서 수집하도록 구현 완료, portal은 미적용

## 프로젝트 현재 구조

```
school_sync/
├── main.py              # 크롤링 CLI
├── ask.py               # LLM Q&A CLI (Claude API)
├── config.py / config.yaml
├── browser.py           # Playwright 세션
├── models.py            # Pydantic 스키마 (12개 모델)
├── normalizer.py        # Raw → Normalized (도메인별 분류)
├── cache.py             # URL+날짜 기반 중복 방지 캐시
├── crawlers/
│   ├── base.py, portal.py, department.py, ndrims.py
│   └── eclass/ (crawler.py, scanner.py, extractors/8개)
├── output/
│   ├── raw/             # eclass, portal, department, ndrims
│   ├── normalized/      # academics/, schedule/, info/, profile/
│   ├── cache/           # collected_posts.json
│   └── downloads/       # 강의자료 파일
└── docs/
    ├── DESIGN.md, HANDOFF.md
    └── NEXT_SESSION.md  # ← 이 파일
```

## 프롬프트

```
school_sync 프로젝트를 이어서 작업하려고 해.
docs/DESIGN.md에 전체 설계, docs/HANDOFF.md에 현재 상태, docs/NEXT_SESSION.md에 이번에 할 작업이 정리되어 있어.

핵심 작업:
1. 강의계획서(syllabus) 정규화 — raw에 데이터 있는데 normalized에 없어서 LLM이 교재/수업계획 질문에 답 못 함
2. 교재 수집 개선 — syllabus extractor가 주교재/부교재 2권만 잡고 나머지 놓침

docs/NEXT_SESSION.md에 상세 내용 있으니 읽고 진행해줘.
```
