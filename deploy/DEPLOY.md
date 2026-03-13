# StudyHub VPS 배포 가이드

## 사전 조건

- VPS: `46.250.251.82` (Ubuntu 24.04, Docker 설치됨)
- 와일드카드 SSL: `*.syworkspace.cloud` 발급 완료
- Cloudflare DNS 관리 가능

## 배포 순서

### 1. DNS 레코드 추가

Cloudflare에서 A 레코드 추가:
- Name: `study`
- Content: `46.250.251.82`
- Proxy: OFF (DNS only)

### 2. VPS에 코드 배포

```bash
cd /opt/apps
git clone <school_sync_repo_url> school_sync
cd school_sync
```

### 3. 환경변수 설정

```bash
cp docker/.env.example /opt/envs/study.env
nano /opt/envs/study.env   # 실제 값 입력
ln -s /opt/envs/study.env docker/.env
```

필수 환경변수:
- `DATA_DIR=/opt/data/study`
- `SCHOOL_USERNAME`, `SCHOOL_PASSWORD`
- `ANTHROPIC_API_KEY`
- `SYOPS_SECRET_KEY` (SyOps와 동일한 값)

### 4. 데이터 디렉토리 생성

```bash
mkdir -p /opt/data/study/output
```

### 5. Docker 빌드 & 실행

```bash
cd /opt/apps/school_sync/docker
docker compose up -d --build
```

### 6. nginx 설정

```bash
sudo cp /opt/apps/school_sync/deploy/nginx/study.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/study.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7. 초기 데이터 크롤링

웹 UI (`https://study.syworkspace.cloud/sync`)에서 크롤링 트리거하거나:

```bash
docker exec -it study python main.py --site eclass --download
```

### 8. SyOps 서비스 등록

`SyOps/backend/services/registry.py`에서 `study` 항목의 `enabled=True`로 변경 후 SyOps 재시작.

## 업데이트

```bash
cd /opt/apps/school_sync
git pull
cd docker
docker compose up -d --build
```

## 로그 확인

```bash
docker logs study -f
docker logs study --tail 50
```
