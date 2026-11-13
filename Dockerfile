# Competitor Analysis -- single image: React UI + FastAPI + IG/FB scrapers.
# Serves everything on one port (4004). Built for linux/arm64 (and amd64).

# ---------- Stage 1: build the React frontend ----------
FROM node:20-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend:/app \
    PYTHON_EXECUTABLE=/usr/local/bin/python \
    CHROME_PATH=/usr/local/bin/chromium-docker \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    DISPLAY=:99 \
    PORT=4004 \
    TZ=Asia/Kolkata

# Chromium + driver (Debian ships arm64 builds; Google Chrome does not),
# Xvfb so "headed" scrapes work without a monitor, fonts for page rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium chromium-driver xvfb xauth tzdata curl ca-certificates \
        fonts-liberation fonts-noto-color-emoji fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY requirements.txt requirements-scrapers.txt
RUN pip install -r backend/requirements.txt -r requirements-scrapers.txt

# App code (see .dockerignore for what is excluded).
COPY backend/ backend/
COPY evaluation/ evaluation/
COPY fb_scraper.py ig_scraper.py schema_store.py selector_overrides.py ./
COPY --from=frontend /build/dist frontend/dist
COPY deploy/chromium-docker /usr/local/bin/chromium-docker
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/chromium-docker /usr/local/bin/entrypoint.sh \
    && mkdir -p data logs fb_session ig_session

EXPOSE 4004
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]
