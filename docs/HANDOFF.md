# school_sync — 핸드오프 컨텍스트

이 문서는 다른 환경(노트북 등)에서 이어서 작업할 때 AI에게 제공하는 컨텍스트 문서이다.

## 현재 상태

- **프로젝트 생성 전**: 설계 문서(`docs/DESIGN.md`)만 작성된 상태
- **코드 없음**: Step 1부터 시작해야 함
- **eclass_crawler는 별도로 존재**: `G:\CS_Study\eclass_crawler\`에 완성된 크롤러가 있음

## 이어서 할 작업

`docs/DESIGN.md`의 "10. 구현 순서 (MVP)" 참조. Step 1부터 시작.

### Step 1 상세 (첫 작업)

1. 프로젝트 기본 파일 생성:
   - `requirements.txt`, `.gitignore`, `.env.example`, `config.py`, `config.yaml`
2. `browser.py` 작성:
   - eclass_crawler의 `browser.py` 기반
   - 멀티 사이트 로그인 지원 (eclass Moodle, SSO, no-auth)
3. `crawlers/base.py` 작성:
   - `BaseCrawler` 추상 클래스
4. eclass_crawler 흡수:
   - `eclass_crawler/extractors/*.py` → `crawlers/eclass/extractors/*.py` 복사
   - `eclass_crawler/scanner.py` → `crawlers/eclass/scanner.py` 복사
   - import 경로 조정 (`from config import` → 상대 import)
   - `crawlers/eclass/crawler.py`에 `EclassCrawler` 클래스 작성
     - 기존 `main.py`의 `run()` 함수 로직을 클래스로 감쌈
5. `main.py` 작성:
   - argparse CLI
   - 사이트 선택 → 해당 크롤러 실행 → raw JSON 저장
6. 동작 확인:
   - `python main.py --site eclass --test`로 기존 기능이 동작하는지 확인

## 참조할 기존 코드

### eclass_crawler 디렉토리 구조
```
eclass_crawler/
├── main.py              # CLI + 파이프라인 오케스트레이션
├── config.py            # 설정 (BASE_URL, 크레덴셜, 딜레이 등)
├── browser.py           # Playwright BrowserSession (로그인 포함)
├── scanner.py           # CourseScan 데이터클래스, scan_course()
├── extractors/          # 8개 extractor
│   ├── courses.py       # extract_courses()
│   ├── syllabus.py      # extract_syllabus()
│   ├── grades.py        # extract_grades()
│   ├── attendance.py    # extract_attendance()
│   ├── notices.py       # extract_boards()
│   ├── assignments.py   # extract_assignments()
│   ├── calendar.py      # extract_calendar_events()
│   └── materials.py     # download_materials()
├── extensions/          # Obsidian 동기화 (Phase 2에서 이식)
│   ├── obsidian_sync.py
│   ├── md_renderer.py
│   └── daily_injector.py
├── sync_config.py       # Obsidian 경로 설정
├── auth.py              # 독립 인증 (참고용)
├── probe.py             # AJAX API 탐색 (참고용)
├── explore.py           # 사이트 구조 탐색 (참고용)
└── explore_course.py    # 과목 페이지 탐색 (참고용)
```

### 핵심 패턴

각 extractor의 공통 시그니처:
```python
async def extract_XXX(page, course_id: int) -> dict | list:
    url = f"{BASE_URL}/path?id={course_id}"
    await page.goto(url, wait_until="networkidle")
    data = await page.evaluate("() => { /* DOM 파싱 JS */ }")
    return data
```

캘린더만 예외적으로 httpx AJAX 호출:
```python
async def extract_calendar_events(cookies: dict, sesskey: str) -> list[dict]:
    async with httpx.AsyncClient(cookies=cookies) as client:
        response = await client.post(AJAX_ENDPOINT, params={"sesskey": sesskey}, json=payload)
```

### lesson-assist의 eclass 데이터 소비 방식

`lesson-assist/src/lesson_assist/eclass.py`의 `EclassData` 클래스가 `eclass_crawler/output/`을 읽어서:
- `get_week_topic(course, date)` → 실라버스 주차 주제
- `get_calendar_events(course)` → 캘린더 이벤트
- `get_downloaded_materials(course)` → 다운로드 자료 경로
- `get_recent_notices(course)` → 최근 공지

config.yaml에서 `eclass.data_dir` 경로를 설정:
```yaml
eclass:
  enabled: true
  data_dir: "G:\\CS_Study\\eclass_crawler\\output"
  course_mapping:
    "과목약칭": "이클래스 정식 과목명"
```

school_sync 완성 후 이 경로를 `school_sync/output/raw/eclass`로 변경하면 호환 가능.

## AI에게 전달할 프롬프트 예시

```
school_sync 프로젝트를 작업하려고 해.
docs/DESIGN.md에 전체 설계가 있고, docs/HANDOFF.md에 현재 상태와 이어서 할 작업이 정리되어 있어.
eclass_crawler (G:\CS_Study\eclass_crawler)의 코드를 흡수해서 통합 크롤러를 만드는 게 목표야.
Step 1부터 시작하자.
```
