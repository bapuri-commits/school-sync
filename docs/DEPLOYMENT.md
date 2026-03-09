# school_sync — VPS 배포 가이드

> ⚠️ **초안 문서** — 각 Stage 진행 시 실제 환경에 맞게 수정될 수 있음.

> Contabo VPS에서 cron으로 대학 시스템 데이터를 주기적으로 크롤링하는 절차.
> DevOps 학습 로드맵 Stage 7에서 사용.
>
> **참조**: DevOps 로드맵 전체는 `SyOps/docs/DEVOPS_ROADMAP.md`를 참조하세요.

---

## 아키텍처 개요

```
[cron (매일 새벽)]
   ↓
[school_sync: eClass + 포탈 + 학과 크롤링]
   ↓
[output/raw/]     → 사이트별 원본 JSON
[output/normalized/] → 정규화된 JSON
```

---

## 사전 요구사항

- Python 3.10+
- Playwright + Chromium (headless)

---

## 환경변수

`.env.example` 참조:

| 변수 | 필수 | 설명 |
|------|------|------|
| `SCHOOL_USERNAME` | ✅ | 학번 |
| `SCHOOL_PASSWORD` | ✅ | 비밀번호 |

---

## 설치

```bash
cd /opt
git clone https://github.com/사용자/school_sync.git
cd school_sync

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium --with-deps

cp .env.example .env
# .env 편집
```

---

## Stage 7 — cron 자동화

```bash
# TODO: Stage 8에서 등록
# 매일 새벽 5시 크롤링
# 0 20 * * * cd /opt/school_sync && /opt/school_sync/.venv/bin/python main.py >> /var/log/school-sync.log 2>&1
```

---

## lesson-assist 연동

school_sync의 `output/raw/eclass/` 데이터를 lesson-assist에서 RAG/컨텍스트로 사용 가능:

```yaml
# lesson-assist config.yaml
eclass:
  data_dir: /opt/school_sync/output/raw/eclass
```

---

## 알려진 이슈

- Playwright 기반이라 VPS headless 환경에서 추가 의존성 필요
- 학교 사이트 인증이 IP 기반 제한이 있을 수 있음 (VPS IP 차단 여부 확인 필요)
- eClass 세션 만료 시 재로그인 로직 확인 필요
- `config.yaml`에서 nDRIMS는 `enabled: false`로 비활성 상태
