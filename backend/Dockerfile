FROM node:22-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend .
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements/base.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend /app
COPY --from=frontend-build /frontend/dist /app/app/static

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

# Liveness only: /health deliberately does not touch the database.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, sys, urllib.request; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/v1/health\").status == 200 else 1)"

# Shell form (not exec-form JSON) so $PORT actually expands -- hosts like Render
# assign their own port via this env var and expect the app to bind to it; falls
# back to 8000 for docker-compose / anywhere PORT isn't set. Migrations run first
# so a fresh/reset database (e.g. a new Neon branch) is never left uninitialized.
# --proxy-headers: behind the platform's TLS terminator the request scheme is
# what marks the session cookie Secure and the client IP is what the demo rate
# limiter keys on; without it every visitor shares the proxy's IP and no cookie
# is ever Secure. Only the platform proxy can reach the container, so '*' is safe.
CMD alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} \
    --proxy-headers --forwarded-allow-ips='*'
