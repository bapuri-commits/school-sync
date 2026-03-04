# school_sync 설계 문서

## 1. 프로젝트 개요

대학 LMS, 포탈, 학과 사이트, 학사 시스템에서 데이터를 크롤링하고, 정규화된 JSON으로 정리하는 통합 도구.

### 목표

- **MVP**: 4개 사이트에서 전체 데이터를 추출하고, 가공하기 편한 정규화 JSON으로 출력
- **Phase 2 (MVP 이후)**: Obsidian 동기화, lesson-assist/The_Agent 등 외부 프로그램 연동

### 배경

- 기존 `eclass_crawler` 프로젝트가 e-Class(Moodle LMS)만 크롤링하고 있었음
- The_Agent의 Phase 3에서 학교 사이트 통합이 계획되어 있었으나 미구현
- `eclass_crawler`를 모듈로 흡수하고, 나머지 사이트를 추가한 **새 프로젝트**로 통합

### 관련 프로젝트

| 프로젝트 | 역할 | school_sync와의 관계 |
|----------|------|---------------------|
| `eclass_crawler` | e-Class LMS 크롤러 (완성) | school_sync에 흡수됨 |
| `lesson-assist` | 강의녹음 → 요약 → 옵시디언 | eclass raw output을 소비 (호환 유지 필요) |
| `The_Agent` | 개인 AI 비서 (할일/일정) | normalized output을 소비 (Phase 2) |
| `The Record` | 옵시디언 볼트 | Obsidian 동기화 대상 (Phase 2) |

---

## 2. 프로젝트 구조

```
school_sync/
├── crawlers/
│   ├── __init__.py
│   ├── base.py                  # BaseCrawler 추상 인터페이스
│   ├── eclass/                  # eclass_crawler 흡수
│   │   ├── __init__.py
│   │   ├── crawler.py           # EclassCrawler (오케스트레이션)
│   │   ├── scanner.py           # 과목 구조 분석 (기존 scanner.py)
│   │   └── extractors/          # 기존 8개 extractor 그대로 이동
│   │       ├── __init__.py
│   │       ├── courses.py       # 수강 과목 목록
│   │       ├── syllabus.py      # 강의계획서
│   │       ├── grades.py        # 성적
│   │       ├── attendance.py    # 출석
│   │       ├── notices.py       # 게시판/공지
│   │       ├── assignments.py   # 활동/과제
│   │       ├── calendar.py      # 캘린더 (AJAX API)
│   │       └── materials.py     # 자료 다운로드
│   ├── portal.py                # 대학 포탈 (학사공지, 학사일정)
│   ├── department.py            # 학과 사이트 (학과공지)
│   └── ndrims.py                # nDRIMS (시간표, 학사일정)
├── models.py                    # Pydantic 정규화 스키마
├── normalizer.py                # Raw → Normalized 변환
├── browser.py                   # Playwright 세션 (멀티 사이트 지원)
├── config.py                    # 통합 설정
├── main.py                      # CLI 진입점
├── output/                      # 생성 데이터 (gitignored)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 3. eclass_crawler 흡수 전략

### 이동할 파일 매핑

| eclass_crawler 원본 | school_sync 대상 | 변경사항 |
|---------------------|-----------------|---------|
| `extractors/*.py` (8개) | `crawlers/eclass/extractors/*.py` | import 경로만 조정 (`from config import` → `from ...config import`) |
| `scanner.py` | `crawlers/eclass/scanner.py` | 동일하게 import 경로 조정 |
| `browser.py` | `browser.py` (루트) | 멀티 사이트 로그인 지원 추가 |
| `config.py` | `config.py` (루트) | 통합 설정으로 확장 |
| `main.py` | `crawlers/eclass/crawler.py` | `EclassCrawler` 클래스로 리팩토링 |
| `extensions/*` | Phase 2에서 이식 | MVP에서는 제외 |

### 핵심 원칙
- 기존 extractor 로직은 **코드 변경 최소화** (import 경로만 조정)
- `output/raw/eclass/` 구조를 기존 `eclass_crawler/output/`과 동일하게 유지 (lesson-assist 호환)

### 기존 eclass_crawler 주요 코드 참조

**config.py** (기존):
```python
BASE_URL = "https://eclass.dongguk.edu"
USERNAME = os.getenv("ECLASS_USERNAME", "")
PASSWORD = os.getenv("ECLASS_PASSWORD", "")
CURRENT_SEMESTER = "2026-1"
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 30.0
GLOBAL_BOARD_IDS = {31, 32, 33}
```

**browser.py** (기존 BrowserSession):
- Playwright 기반 Chromium 헤드리스 브라우저
- Moodle 로그인 → sesskey/쿠키 추출
- `create_session(headless=True)` → BrowserSession 반환

**scanner.py** (기존 CourseScan):
- `@dataclass CourseScan`: course_id, course_name, features, boards, downloadable_resources
- URL 패턴 매칭으로 사용 가능한 기능 탐색
- 활동 모듈 타입 집계 (assign, quiz, resource, folder 등)

**main.py 파이프라인** (기존):
1. Phase 1: 구조 분석 (`scan_course` for each course)
2. Phase 2: 스캔 기반 데이터 추출 (`extract_course_data`)
3. 캘린더는 AJAX API로 별도 추출
4. 과목별 JSON + 통합 semester JSON 저장
5. (옵션) Obsidian 동기화

---

## 4. 크롤러 설계

### 4.1 공통 인터페이스

```python
from abc import ABC, abstractmethod

class BaseCrawler(ABC):
    site_name: str  # "eclass", "portal", "department", "ndrims"

    @abstractmethod
    async def crawl(self, session: BrowserSession, **opts) -> dict:
        """크롤링 실행. 사이트별 raw dict 반환."""
        ...

    @abstractmethod
    def requires_auth(self) -> bool:
        """SSO 로그인이 필요한지 여부."""
        ...
```

### 4.2 인증 전략

`browser.py`에 사이트별 로그인 분기:

| 사이트 | 인증 | 방식 |
|--------|------|------|
| eClass | 필요 | Moodle 로그인 (기존 코드 그대로) |
| nDRIMS | 필요 | SSO 로그인 (같은 학번/비번, 다른 로그인 페이지) |
| 포탈 | 불필요 (공개) | `BrowserSession.start()` 후 바로 사용 |
| 학과 | 불필요 (공개) | 동일 |

크레덴셜: `.env`의 `SCHOOL_USERNAME`, `SCHOOL_PASSWORD` 하나로 모든 사이트 대응.

### 4.3 사이트별 추출 대상

#### eClass (기존 기능 유지)
- 과목 목록, 강의계획서, 성적, 출석, 게시판, 활동/과제, 캘린더, 자료 다운로드
- 8개 extractor 모두 동작 확인됨

#### 대학 포탈
- 학사 공지사항 (게시판 스크래핑)
- 학사일정 (학사 캘린더 — 개강/중간/기말/종강/수강신청 등)
- 장학 공지 (선택)
- **구현 시**: 먼저 explore 스크립트로 페이지 구조 탐색 필요

#### 학과 사이트
- 학과 공지사항
- 행사/세미나 정보 (있을 경우)
- **구현 시**: 먼저 explore 스크립트로 페이지 구조 탐색 필요

#### nDRIMS (리스크 있음)
- 수강 시간표 (요일, 시간, 교실)
- 학사일정 (포탈과 겹칠 수 있음, 교차검증용)
- **리스크**: SSO 흐름이 다르거나, 페이지가 JS-heavy일 수 있음
- 실패 시 graceful skip (MVP에 영향 없음)

---

## 5. 정규화 모델 (Pydantic)

### models.py

```python
from datetime import datetime, date, time
from pydantic import BaseModel

class Course(BaseModel):
    id: int
    name: str
    short_name: str        # 정규화된 짧은 이름 ("자료구조")
    professor: str
    url: str

class Deadline(BaseModel):
    """통합 마감 뷰 — 핵심 산출물.
    캘린더 이벤트, 과제 마감, 공지에서 추출한 날짜 정보를 병합."""
    title: str
    course_name: str | None
    due_at: datetime
    source: str            # "calendar" | "assignment" | "notice"
    source_site: str       # "eclass" | "portal" | "department"
    url: str
    d_day: int             # 오늘 기준 남은 일수

class Assignment(BaseModel):
    course_name: str
    title: str
    activity_type: str     # "assign" | "quiz" | "vod" | ...
    deadline: datetime | None
    url: str

class CalendarEvent(BaseModel):
    title: str
    course_name: str | None
    start_at: datetime
    end_at: datetime | None
    event_type: str
    url: str
    source_site: str

class Notice(BaseModel):
    title: str
    board_name: str
    author: str
    date: str
    url: str
    source_site: str       # "eclass" | "portal" | "department"

class AcademicSchedule(BaseModel):
    title: str
    start_date: date
    end_date: date | None
    category: str          # "개강" | "중간고사" | "기말고사" | "수강신청" | ...
    source_site: str

class TimetableEntry(BaseModel):
    course_name: str
    day_of_week: int       # 0=월 ~ 4=금
    start_time: time
    end_time: time
    location: str
    professor: str
```

### 현재 eclass raw 데이터의 문제점 (normalizer가 해결해야 할 것)

1. **스키마 없음**: 모든 extractor가 plain dict 반환, pydantic 미사용
2. **키 이름 불일치**: 게시판 포스트가 `{"제목": "...", "작성일": "..."}` 또는 `{"col_0": "...", "col_1": "..."}` — HTML 테이블 헤더에 의존
3. **과제에 deadline 필드 없음**: `info` 텍스트에 "마감: 2026-03-15" 같은 문자열이 그냥 들어감
4. **캘린더 Unix timestamp**: `{"time_start": 1741046400}` — ISO datetime 변환 필요
5. **통합 마감 뷰 없음**: 과제/캘린더/공지에 흩어진 마감 정보를 모아볼 방법 없음

lesson-assist의 `eclass.py`에서 이미 3중 fallback으로 대응 중:
```python
"title": post.get("제목", post.get("title", post.get("col_1", "")))
```

---

## 6. 출력 구조

```
output/
├── raw/                         # 사이트별 원본 (기존 호환)
│   ├── eclass/
│   │   ├── 2026-1_semester.json # 기존 eclass_crawler format 그대로
│   │   ├── scan_result.json
│   │   └── courses/             # 과목별 JSON
│   ├── portal/
│   │   ├── notices.json
│   │   └── academic_calendar.json
│   ├── department/
│   │   └── notices.json
│   └── ndrims/
│       └── timetable.json
├── normalized/                  # 정규화 (새로운 핵심 산출물)
│   ├── deadlines.json           # 통합 마감 (D-day 포함, due_at 순 정렬)
│   ├── courses.json             # 과목 메타
│   ├── assignments.json         # 과제 (ISO datetime)
│   ├── calendar.json            # 캘린더 (ISO datetime)
│   ├── notices.json             # 통합 공지 (4개 사이트 병합)
│   ├── academic_schedule.json   # 학사일정
│   ├── timetable.json           # 시간표
│   ├── grades.json              # 성적
│   └── attendance.json          # 출석
└── downloads/                   # 자료 파일 (eclass)
```

- `raw/`: 기존 eclass_crawler, lesson-assist와 호환성 유지
- `normalized/`: The_Agent, Obsidian 동기화 등 다운스트림에서 바로 사용 가능

---

## 7. CLI 인터페이스

```bash
# 전체 크롤링 + 정규화 (MVP 기본)
python main.py

# 특정 사이트만
python main.py --site eclass
python main.py --site portal department

# eclass 세부 옵션 (기존 호환)
python main.py --site eclass --course 1 3 --only syllabus grades
python main.py --site eclass --download

# 정규화만 (이미 raw가 있을 때)
python main.py --normalize-only

# 테스트
python main.py --site eclass --test
```

---

## 8. 데이터 흐름

```
┌─────────────────────────────────────────────────┐
│              Phase 1: 크롤링                      │
│  EclassCrawler  PortalCrawler  DeptCrawler  ...  │
└────────┬──────────┬──────────┬──────────┬────────┘
         │          │          │          │
         ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────┐
│              Raw Output (사이트별 JSON)            │
│  eclass/       portal/     department/   ndrims/  │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              Normalizer                           │
│  Raw dict → Pydantic 모델 → 정규화 JSON           │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              Normalized Output                    │
│  deadlines / assignments / calendar / notices     │
│  academic_schedule / timetable / grades / ...     │
└─────────────────────────────────────────────────┘
```

---

## 9. 설정 구조

### config.yaml (예시)

```yaml
semester: "2026-1"
request_delay: 0.5
request_timeout: 30.0

sites:
  eclass:
    base_url: "https://eclass.dongguk.edu"
    enabled: true
    global_board_ids: [31, 32, 33]
  portal:
    base_url: "https://www.dongguk.edu"
    enabled: true
  department:
    base_url: "https://ai.dongguk.edu"
    enabled: true
  ndrims:
    base_url: "https://ndrims.dongguk.edu"
    enabled: true

output_dir: "output"
```

### .env

```
SCHOOL_USERNAME=학번
SCHOOL_PASSWORD=비밀번호
```

---

## 10. 구현 순서 (MVP)

### Step 1: 프로젝트 셋업 + eclass 흡수
- `school_sync/` 프로젝트 생성 (requirements.txt, .gitignore, config)
- `BaseCrawler`, `browser.py`, `config.py` 작성
- eclass_crawler의 extractors, scanner를 `crawlers/eclass/`로 이동
- import 경로 조정, `EclassCrawler` 클래스 작성
- 기존 eclass 기능이 동일하게 동작하는지 확인

### Step 2: Pydantic 모델 + Normalizer
- `models.py`에 정규화 스키마 정의
- `normalizer.py` 작성: eclass raw → 정규화 변환
  - calendar의 Unix timestamp → ISO datetime
  - activities → assignments (deadline 파싱)
  - boards → notices (키 정규화)
  - 통합 deadlines 생성

### Step 3: 대학 포탈 크롤러
- 포탈 페이지 구조 탐색 (explore 스크립트)
- 학사공지 추출
- 학사일정 추출
- 정규화 연동

### Step 4: 학과 사이트 크롤러
- 학과 사이트 페이지 구조 탐색
- 학과 공지 추출
- 정규화 연동

### Step 5: nDRIMS 크롤러 (리스크 있음)
- SSO 로그인 흐름 파악
- 시간표 추출 시도
- 학사일정 추출 시도
- 실패 시 graceful skip

### Step 6: 통합 CLI + 마무리
- `main.py` 통합 CLI
- 전체 파이프라인 테스트
- README 작성

---

## 11. Phase 2 (MVP 이후): 외부 연동

MVP 완료 후 `extensions/` 디렉토리에 연동 모듈을 추가한다:

- **Obsidian 동기화**: eclass_crawler의 `extensions/`를 이식하되, normalized 데이터 기반으로 리팩토링. 마커를 `<!-- school-sync-start -->` / `<!-- school-sync-end -->`로 확장
- **lesson-assist 어댑터**: lesson-assist의 `eclass.py`가 `output/raw/eclass/`를 읽도록 경로만 변경하면 호환 가능
- **The_Agent 연동**: normalized JSON을 The_Agent의 inbox API로 전송하는 어댑터, 또는 The_Agent가 직접 읽는 구조

---

## 12. 리스크

- **nDRIMS**: SSO 흐름이 다르거나, 페이지가 완전히 JS 렌더링이면 추출이 어려울 수 있음. 실패해도 MVP에는 영향 없음
- **포탈/학과 사이트 구조 변경**: 공개 페이지는 리디자인될 수 있음. selector 기반이라 깨지기 쉬움
- **기존 호환성**: `output/raw/eclass/` 구조를 기존 eclass_crawler와 동일하게 유지해야 lesson-assist가 깨지지 않음

---

## 13. 의존성

```
httpx
playwright
pydantic
python-dotenv
pyyaml
```

Playwright Chromium 별도 설치 필요: `python -m playwright install chromium`
