# school_sync 설계 문서

## 1. 프로젝트 개요

대학 LMS, 포탈, 학과 사이트, 학사 시스템에서 데이터를 크롤링하고, 정규화된 JSON으로 정리하며, LLM 기반 자연어 Q&A를 제공하는 **독립적인 학교 생활 어시스턴트**.

### 목표

- **데이터 수집**: 4개 사이트(eClass, 포탈, 학과, nDRIMS)에서 학교 데이터 통합 크롤링
- **정규화**: 도메인별(academics/schedule/info/profile) 분류된 JSON 출력
- **LLM Q&A**: 크롤링 데이터 기반 자연어 질의 (성적 계산, 시간표 조회, 졸업 요건 등)
- **The_Agent 연동**: 파일 기반 인터페이스로 상위 AI 비서에 데이터 제공

### 아키텍처

```
school_sync (독립 실행 가능)
├── 크롤링 (main.py)             → output/raw/
├── 정규화 (normalizer.py)        → output/normalized/
├── 학습 컨텍스트 (context_export) → output/context/   ← lesson-assist 소비
├── 브리핑 (briefing.md)          → The_Agent/사용자 소비
└── Q&A (ask.py)                  → 독립 CLI 인터페이스

The_Agent (미래 통합)
├── school_sync  ← 학교 생활 (파일 인터페이스)
├── lesson-assist ← 수업 녹음/요약
└── ...
```

### 관련 프로젝트

| 프로젝트 | 역할 | school_sync와의 관계 |
|----------|------|---------------------|
| `eclass_crawler` | e-Class LMS 크롤러 (완성) | school_sync에 흡수됨 |
| `lesson-assist` | 학습 패키징 + 노트 생성 | `output/context/` 과목별 컨텍스트 + `output/downloads/` 수업자료를 소비 |
| `The_Agent` | 개인 AI 비서 | normalized output + briefing.md를 소비 |
| `The Record` | 옵시디언 볼트 | Obsidian 동기화 대상 (미래) |

---

## 2. 프로젝트 구조

```
school_sync/
├── main.py                         # 통합 CLI (크롤링 + 정규화)
├── ask.py                          # LLM Q&A 인터페이스
├── config.py                       # config.yaml 로드 + 레거시 호환
├── config.yaml                     # 사이트별 설정
├── browser.py                      # Playwright BrowserSession
├── models.py                       # Pydantic 정규화 스키마
├── normalizer.py                   # Raw → Normalized 변환
├── context_export.py               # 과목별 학습 컨텍스트 생성 → output/context/
├── requirements.txt
├── .env.example
├── .gitignore
├── explore_ndrims.py               # nDRIMS 구조 탐색 (개발용)
├── docs/
│   ├── DESIGN.md
│   └── HANDOFF.md
└── crawlers/
    ├── __init__.py
    ├── base.py                     # BaseCrawler 추상 클래스
    ├── portal.py                   # 포탈 (학사공지, 장학공지, 학사일정)
    ├── department.py               # 학과 (공지, 특강/공모전/취업)
    ├── ndrims.py                   # nDRIMS (프로필, 성적, 시간표)
    └── eclass/
        ├── __init__.py
        ├── crawler.py              # EclassCrawler
        ├── scanner.py              # 과목 구조 분석
        └── extractors/             # 8개 extractor
```

---

## 3. 데이터 흐름

```
┌─────────────────────────────────────────────────┐
│              크롤링 (main.py)                     │
│  EclassCrawler  PortalCrawler  DeptCrawler  ...  │
└────────┬──────────┬──────────┬──────────┬────────┘
         ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────┐
│              Raw Output (사이트별)                 │
│  eclass/       portal/     department/   ndrims/  │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│              Normalizer                           │
│  도메인별 분류 + briefing.md 생성                   │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│              Normalized Output                    │
│  academics/ schedule/ info/ profile/ briefing.md  │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│              소비자                                │
│  ask.py (Q&A)  │  The_Agent  │  Obsidian (미래)   │
└─────────────────────────────────────────────────┘
```

---

## 4. 출력 구조

```
output/
├── raw/                              # 사이트별 원본
│   ├── eclass/
│   │   ├── 2026-1_semester.json
│   │   ├── scan_result.json
│   │   └── courses/
│   ├── portal/
│   │   └── portal.json
│   ├── department/
│   │   └── notices.json
│   └── ndrims/
│       └── ndrims.json
├── normalized/                       # 도메인별 정규화
│   ├── briefing.md                   # 오늘의 브리핑
│   ├── academics/
│   │   ├── courses.json
│   │   ├── deadlines.json
│   │   ├── assignments.json
│   │   ├── attendance.json
│   │   ├── grades.json
│   │   └── syllabus.json             # 강의계획서 (교재/수업계획/교수정보)
│   ├── schedule/
│   │   ├── calendar.json
│   │   ├── academic_schedule.json
│   │   └── timetable.json
│   ├── info/
│   │   └── notices.json
│   └── profile/
│       ├── student.json
│       ├── grade_history.json
│       └── graduation_requirements.json
└── downloads/                        # eclass 자료 파일
```

---

## 5. CLI 인터페이스

### 크롤링 + 정규화

```bash
python main.py                              # 전체 크롤링 + 정규화
python main.py --site eclass                # eClass만
python main.py --site portal department     # 포탈 + 학과만
python main.py --site ndrims                # nDRIMS (브라우저 열림)
python main.py --normalize-only             # 정규화만 재실행
python main.py --site eclass --test         # eClass 테스트 (첫 과목만)
python main.py --site eclass --download     # 수업자료 다운로드 포함
```

### LLM Q&A

```bash
python ask.py                               # 대화 모드 (웹검색 ON)
python ask.py "오늘 시간표 알려줘"            # 단일 질문
python ask.py --refresh                      # 정규화 재실행 후 대화
python ask.py --no-search                    # 웹검색 OFF (로컬 데이터만)
```

---

## 6. 사이트별 크롤러

### eClass (인증 필요 — Moodle 로그인)
- 과목 목록, 강의계획서, 성적, 출석, 게시판, 활동/과제, 캘린더, 자료 다운로드
- 8개 extractor + scanner 구조 (eclass_crawler에서 흡수)

### 포탈 (공개)
- 학사공지 (HAKSANOTICE), 장학공지 (JANGHAKNOTICE)
- 학사일정 (schedule_info_seq=22)

### 학과 사이트 (공개)
- 학과 공지사항, 특강/공모전/취업공지

### nDRIMS (SSO 로그인 — 수동)
- CLX 프레임워크 기반 SPA
- 메뉴 클릭 → API 응답 가로채기 방식
- 학적 프로필, 전체 성적 (25과목), 개인 시간표

---

## 7. 정규화 모델 (models.py)

- Course, CalendarEvent, Deadline, Assignment
- Notice, AttendanceRecord, GradeItem
- TimetableEntry, AcademicSchedule
- StudentProfile, NormalizedOutput

---

## 8. LLM Q&A (ask.py)

- Anthropic Claude API 사용 + 빌트인 웹검색(`web_search_20250305`)
- **하이브리드 모드**: 로컬 크롤링 데이터 우선 → 부족하면 웹검색 자동 수행
- 질문 키워드 분류 → 관련 데이터만 로드 (토큰 예산 30K자 제한)
- 스마트 필터링: notices(최근 7일/과목별), attendance(결석만), grades(과목별), schedule(향후 30일)
- 데이터 출처 인용 (`[출처: ...]`, `[출처: 웹검색]`)
- `--no-search`: 웹검색 비활성화 (로컬 데이터만 사용)

---

## 9. The_Agent 연동

school_sync는 별도 서버/API 없이 **파일 기반 인터페이스**:

- `briefing.md`: The_Agent가 매일 읽어서 빠른 브리핑 제공
- `normalized/*.json`: MCP 도구로 상세 데이터 직접 읽기
- `graduation_requirements.json`: 졸업 요건 (수동 관리)

The_Agent 쪽에서 school_sync 경로를 등록하면 연동 완료.

---

## 10. 의존성

```
httpx
playwright
pydantic
python-dotenv
pyyaml
anthropic
```

Playwright Chromium: `python -m playwright install chromium`

---

## 11. MCP화 계획

school_sync와 lesson-assist는 궁극적으로 **MCP 서버**로 전환하여 The_Agent가 도구로 호출하는 구조를 목표로 한다. 현재는 단독 프로그램으로 동작하되, 핵심 로직이 함수 단위로 분리되어 있어 MCP tool 래핑이 용이한 상태.

```
The_Agent (MCP 클라이언트)
├── school_sync MCP 서버
│   ├── tool: crawl(site)
│   ├── tool: get_timetable(day)
│   ├── tool: get_deadlines(days)
│   ├── tool: get_grades()
│   ├── tool: ask(question)
│   └── resource: briefing.md
├── lesson-assist MCP 서버
│   ├── tool: summarize_lecture(recording)
│   ├── tool: get_week_topic(course, date)
│   └── resource: lecture_notes/
└── ...
```

구현 시점: The_Agent 작업 시. `mcp_server.py` 하나 추가하는 수준.

## 12. 미래 개선 방향

- Obsidian 동기화 (normalized → 마크다운)
- 공지 본문 크롤링 (현재 제목+URL만)
- 시간표 구조화 (자연어 → day_of_week/start_time/end_time)
- 데이터 변경 추적 (diff/이력)
- nDRIMS 졸업 이수 현황 자동 추출
