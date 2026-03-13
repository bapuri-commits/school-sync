# StudyHub — school_sync + lesson-assist 통합 서비스
# Multi-stage: Node.js(프론트 빌드) → Python(서비스)

# --- Stage 1: Frontend build ---
FROM node:22-slim AS frontend-build

WORKDIR /build
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build

# --- Stage 2: Python service ---
FROM python:3.12-slim

WORKDIR /app

# Playwright 시스템 의존성 + Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

# school_sync 소스
COPY . .

# 프론트엔드 빌드 결과 복사
COPY --from=frontend-build /build/dist/ ./web/frontend/dist/

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
