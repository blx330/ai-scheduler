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

# Shell form (not exec-form JSON) so $PORT actually expands -- hosts like Render
# assign their own port via this env var and expect the app to bind to it; falls
# back to 8000 for docker-compose / anywhere PORT isn't set. Migrations run first
# so a fresh/reset database (e.g. a new Neon branch) is never left uninitialized.
CMD alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
