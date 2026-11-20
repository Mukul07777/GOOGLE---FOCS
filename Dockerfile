# ---- web build ----
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# docker build --build-arg VITE_EDITION=bridge: the event build (opens on the bridge, shows only its screens)
ARG VITE_EDITION=""
ENV VITE_EDITION=$VITE_EDITION
# docker build --build-arg VITE_SENTRY_DSN=<focs-frontend DSN>: the web app's error reports (empty = off)
ARG VITE_SENTRY_DSN=""
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN
RUN npm run build

# ---- api ----
FROM python:3.12-slim
# A container is a server for other people: production unless told otherwise (no dev shortcuts such as test payments
# or email codes shown on screen, no API docs, and it refuses to start without a strong SECRET_KEY)
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENV=production
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=web /web/dist /app/frontend/dist
# run as an ordinary user: /data (the compose volume) and the backend folder (a plain `docker run`) stay writable
RUN useradd --create-home --uid 1000 focs && mkdir -p /data && chown -R focs:focs /data /app/backend
USER focs
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3   CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1
# one worker: live classes and rate limits are in memory. Room messages are small: 64 KB per websocket message.
# Forwarded headers (https, the visitor address) are trusted only from Caddy reaching us over Docker's bridge (172.16/12)
# or loopback, so a visitor can't fake them; no Server header (the version helps nobody but an attacker)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1,172.16.0.0/12", "--no-server-header", "--workers", "1", "--ws-max-size", "65536", "--timeout-keep-alive", "75"]
