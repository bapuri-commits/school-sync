# school_sync — 핸드오프 컨텍스트

## 현재 상태: v1.0 완성

독립적인 학교 생활 어시스턴트. 4개 사이트 크롤링 + 정규화 + LLM Q&A 전부 동작.

### 실행 방법

```bash
# 전체 크롤링 + 정규화 (eclass/portal/department는 자동, ndrims는 수동 로그인)
python main.py

# LLM Q&A
python ask.py

# 개별 사이트
python main.py --site eclass
python main.py --site portal department
python main.py --site ndrims          # 브라우저 열림, SSO 수동 로그인
```

### 환경 설정

`.env` 필요:
```
SCHOOL_USERNAME=학번
SCHOOL_PASSWORD=비밀번호
ANTHROPIC_API_KEY=sk-ant-...
```

### 파일 구조

```
school_sync/
├── main.py                 # 크롤링 CLI
├── ask.py                  # LLM Q&A CLI
├── config.py / config.yaml # 설정
├── browser.py              # Playwright 세션
├── models.py               # Pydantic 스키마
├── normalizer.py           # Raw → Normalized
├── explore_ndrims.py       # nDRIMS 구조 탐색 (개발용)
├── crawlers/
│   ├── base.py
│   ├── portal.py
│   ├── department.py
│   ├── ndrims.py
│   └── eclass/ (8 extractors + scanner + crawler)
└── output/
    ├── raw/     (사이트별 원본)
    └── normalized/
        ├── briefing.md
        ├── academics/  (courses, deadlines, assignments, attendance, grades)
        ├── schedule/   (calendar, academic_schedule, timetable)
        ├── info/       (notices)
        └── profile/    (student, grade_history, graduation_requirements)
```

### The_Agent 연동

파일 기반 인터페이스:
- `output/normalized/briefing.md` → 매일 브리핑
- `output/normalized/**/*.json` → MCP 도구로 상세 조회

### 알려진 제한사항

- nDRIMS SSO 로그인은 수동 (자동화 불가)
- eclass 캘린더는 학기 초에 과제가 없으면 빈 결과
- 공지는 제목+URL만 (본문 미수집)
- 시간표는 자연어 형태 (구조화 미완)

### 미래 작업

1. Obsidian 동기화
2. 공지 본문 크롤링
3. 시간표 구조화
4. 데이터 변경 추적
5. The_Agent MCP 도구 구현

### 환경별 경로

| 환경 | 경로 |
|------|------|
| 노트북 (C:) | `C:\Users\chois\CS_Study_SY\school_sync\` |
| 데스크탑 (G:) | `G:\CS_Study\school_sync\` |
