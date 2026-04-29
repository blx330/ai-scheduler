# AI Scheduler

I built this as a backend-first scheduling project to practice real scheduling logic, not just CRUD.

At a high level, it does three things:
- stores users, events, and manual availability
- pulls busy time from Google Calendar (when connected)
- generates and ranks feasible practice slots with deterministic scoring

The API and a small demo UI are both served by FastAPI from the same process (`backend/app/main.py` mounts `backend/app/static`).

## What the project does right now

Current flow:
1. Create users
2. Add manual availability (explicit free intervals)
3. Optionally connect Google Calendar and sync busy intervals
4. Create events with required participants
5. Run planning (`/api/v1/planning-runs`) to get top recommendations
6. Confirm selected results and optionally create Google Calendar events

Scheduling behavior in this codebase:
- required attendees are a hard constraint for primary recommendations; if not enough fully-feasible options exist, fallback suggestions may include missing required attendees
- optional attendees are score modifiers
- candidate generation is limited to 8:00 AM -> 12:00 AM in organizer local time
- 12:00 AM -> 8:00 AM is a hard forbidden window
- ranking is deterministic (score, then tie-breakers)

## Code structure (actual repo layout)

### Root
- `backend/` - main Python app
- `infra/compose.yaml` - local Docker Compose (Postgres + API service)
- `.env.example` - sample env file used for local setup
- `PROJECT_SNAPSHOT_2026-04-10.md` - project snapshot notes

### Backend app
- `backend/app/main.py` - app bootstrap, dependency wiring, router registration, static UI mount
- `backend/app/api/` - FastAPI layer (routes, request/response schemas, dependency helpers)
  - `routers/` - endpoints (`users`, `events`, `planning`, `availability`, `practices`, `google_calendar`, `health`)
  - `schemas/` - Pydantic API contracts
  - `deps.py` - shared request dependencies (db session, settings, integrations)
- `backend/app/application/services/` - use-case orchestration
  - `planning_service.py` - planning run orchestration + confirmation flow
  - `google_calendar_service.py` - OAuth, sync, event create/delete behavior
  - `user_service.py`, `event_service.py`, `availability_service.py` - domain workflow + persistence coordination
- `backend/app/domain/` - framework-independent scheduling logic
  - `scheduling/` - candidate generation, scoring, global planner
  - `availability/` - interval operations and availability semantics
  - `preferences/` - preference models/normalization
  - `common/` - shared domain utilities
- `backend/app/infrastructure/` - config, DB models/session, external adapters
  - `config.py` - env-backed settings
  - `db/` - SQLAlchemy models + session/base/types
  - `integrations/google_calendar/client.py` - Google Calendar HTTP client
  - `integrations/llm/profile_preference_parser.py` - free-text preference parser (stub or Groq-backed)
- `backend/app/static/` - demo frontend assets served by FastAPI

### Database and migrations
- `backend/alembic.ini` - Alembic config
- `backend/alembic/versions/` - migration history

### Tests
- `backend/tests/integration/api/` - API integration tests
- `backend/tests/unit/domain/` - scheduling and interval unit tests
- `backend/tests/unit/infrastructure/` - integration client unit tests
- `backend/tests/conftest.py` - shared test setup/fixtures

## Requirements

- Python `3.11+` for local development (`backend/.venv_local` currently uses 3.11)
- Python `3.12` in Docker (`backend/Dockerfile`)
- Docker + Docker Compose (for local Postgres, and optional full Docker run)

No Node.js setup is required for local development in this repo.

## Environment variables

Create your local env file:

```bash
cp .env.example .env
```

For the default Docker DB flow in this README, make sure `.env` has:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/scheduler
```

Variables currently read by backend settings (`backend/app/infrastructure/config.py`):
- `DATABASE_URL`
- `APP_BASE_URL`
- `FRONTEND_URL`
- `GROQ_API_KEY` (optional; if set, Groq parser is used)
- `OAUTH_STATE_SECRET` (needed for Google OAuth flow)
- `GOOGLE_CLIENT_ID` (needed for Google OAuth flow)
- `GOOGLE_CLIENT_SECRET` (needed for Google OAuth flow)
- `GOOGLE_REDIRECT_URI` (needed for Google OAuth flow)

Notes:
- `.env.example` also includes `PARSER_MODE` and `FEATHER_API_KEY`, but those are not currently consumed by `Settings`.
- If Google OAuth env vars are missing, core scheduling still runs, but Google connection/sync/event creation will not.

### Google Calendar OAuth setup (required for Connect Google Calendar)

1. Go to Google Cloud Console and create/select a project.
2. Enable the Google Calendar API.
3. Configure OAuth consent screen.
4. Create an OAuth Client ID (Web application).
5. Add this redirect URI exactly:

```text
http://localhost:8000/api/v1/google/oauth/callback
```

6. Put your values in `.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/google/oauth/callback
```

7. Restart the API after editing `.env`.

## Install and run (local)

### 1) Start Postgres

From repo root:

```bash
docker compose -f infra/compose.yaml up -d db
```

Wait until Postgres is healthy before running migrations:

```bash
docker compose -f infra/compose.yaml logs db
```

Look for a line like `database system is ready to accept connections`.

### 2) Install Python dependencies

```bash
cd backend
python3 -m venv .venv_local
source .venv_local/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/dev.txt
```

### 3) Run DB migrations

From `backend/` with your venv active:

```bash
alembic upgrade head
```

If you get `fe_sendauth: no password supplied`, your `DATABASE_URL` in `.env` is missing credentials. Set it to:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/scheduler
```

### 4) Run the app

From `backend/` with the venv active:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:
- `http://localhost:8000/` (demo UI)
- `http://localhost:8000/docs` (FastAPI docs)

If you see `ModuleNotFoundError` errors around app imports, make sure you're in `backend/` and your venv is active:

```bash
cd backend
source .venv_local/bin/activate
alembic upgrade head
```

## Run with Docker instead (API + DB)

From repo root:

```bash
docker compose -f infra/compose.yaml up --build
```

Then run migrations in the API container before using the app:

```bash
docker compose -f infra/compose.yaml exec api alembic upgrade head
```

This uses:
- Postgres on `5432`
- API/UI on `http://localhost:8000`

## Tests

From `backend/` with your venv active:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache PYTHONPATH=. python -m pytest -q
```

## Current limitations

- no auth/permissions system yet
- no recurring availability support
- no background jobs (sync/planning work happens inline)
- Google integration is functional for demo/dev, but not hardened as production OAuth infra
- frontend demo UI is functional, but not yet polished for usability or visual design
