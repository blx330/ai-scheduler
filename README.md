# AI Scheduler

I built this as a backend-first scheduling project to practice real scheduling logic, not just CRUD.

At a high level, it does three things:
- stores users, events, and manual availability
- pulls busy time from Google Calendar (when connected)
- generates and ranks feasible practice slots with deterministic scoring

The API is served by FastAPI (`backend/`). The UI is a React SPA (`frontend/`) that talks to the API over `/api/v1`. In production/Docker, the built React assets are bundled into the FastAPI image and served from the same process and port — see [Build & deploy](#run-with-docker-single-command-deploy).

## What the project does right now

Current flow:
1. Create users
2. Add manual availability (explicit free intervals)
3. Optionally connect Google Calendar — once connected, busy intervals sync automatically on a timer (also syncable on demand)
4. Create events with required participants
5. Run planning (`/api/v1/planning-runs`) to get top recommendations
6. Confirm selected results and optionally create Google Calendar events

The calendar page shows a week grid with per-dance session blocks (drag to reschedule) and a Members panel where each member gets a checkbox and a unique color — toggle a member to show or hide their Google-derived busy time on the grid, labeled with their name.

Scheduling behavior in this codebase:
- required attendees are a hard constraint for primary recommendations; if not enough fully-feasible options exist, fallback suggestions may include missing required attendees
- optional attendees are score modifiers
- candidate generation is limited to 8:00 AM -> 12:00 AM in organizer local time
- 12:00 AM -> 8:00 AM is a hard forbidden window
- ranking is deterministic (score, then tie-breakers)

## Code structure (actual repo layout)

### Root
- `backend/` - main Python app
- `frontend/` - React + TypeScript SPA (Vite, Tailwind CSS, shadcn/ui)
- `infra/compose.yaml` - Docker Compose (Postgres + API, API image bundles the built frontend)
- `.env.example` - sample env file used for local setup
- `PROJECT_SNAPSHOT_2026-04-10.md` - project snapshot notes

### Backend app
- `backend/app/main.py` - app bootstrap, dependency wiring, router registration, static frontend mount
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
  - `integrations/llm/profile_preference_parser.py` - free-text preference parser (stub or Gemini-backed)
- `backend/app/static/` - build output only (gitignored); populated by the Docker build from `frontend/dist`, empty otherwise

### Frontend app
- `frontend/src/api/` - typed fetch client + TypeScript types matching the backend Pydantic schemas
- `frontend/src/hooks/` - TanStack Query hooks per resource (users, availability, events, planning, calendar, google-calendar)
- `frontend/src/pages/` + `frontend/src/components/` - member/availability/preference management, event scheduling, planning + confirmation, Google Calendar sync, weekly calendar overview with a per-member visibility/color panel and drag-to-reschedule
- `frontend/src/components/ui/` - hand-built shadcn/ui primitives (Radix + class-variance-authority + tailwind-merge)
- See `frontend/README.md` for frontend-specific dev notes.

### Database and migrations
- `backend/alembic.ini` - Alembic config
- `backend/alembic/versions/` - migration history

### Tests
- `backend/tests/integration/api/` - API integration tests
- `backend/tests/unit/domain/` - scheduling and interval unit tests
- `backend/tests/unit/infrastructure/` - integration client unit tests
- `backend/tests/conftest.py` - shared test setup/fixtures

## Requirements

- Python `3.11+` for local backend development (`backend/.venv_local` currently uses 3.11)
- Python `3.12` in Docker (`backend/Dockerfile`)
- Node.js `20.19+` (or `22.12+`) and npm for local frontend development
- Docker + Docker Compose (for local Postgres, and the single-command full-stack run)

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
- `FRONTEND_URL`
- `GEMINI_API_KEY` (optional; if set, the Gemini-backed preference parser is used, model `gemini-2.5-flash` via the `google-genai` SDK; if unset, a deterministic stub parser is used instead)
- `OAUTH_STATE_SECRET` (needed for Google OAuth flow)
- `GOOGLE_CLIENT_ID` (needed for Google OAuth flow)
- `GOOGLE_CLIENT_SECRET` (needed for Google OAuth flow)
- `GOOGLE_REDIRECT_URI` (needed for Google OAuth flow)
- `AUTO_SYNC_ENABLED` (default `true`) - background sweep that refreshes every connected member's Google busy time on a timer, in addition to the manual "Sync busy time" button
- `AUTO_SYNC_INTERVAL_MINUTES` (default `15`) - how often the sweep runs
- `AUTO_SYNC_HORIZON_DAYS` (default `30`) - how far ahead each sweep syncs, matching the manual sync window

Notes:
- Get a Gemini API key from Google AI Studio (https://aistudio.google.com/apikey) and set `GEMINI_API_KEY` in `.env`.
- If Google OAuth env vars are missing, core scheduling still runs, but Google connection/sync/event creation will not.
- The frontend has no build-time or runtime env vars of its own — it always calls the API at a relative `/api/v1/...` path (same-origin in Docker; proxied to `localhost:8000` by Vite in local dev).

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

## Run with Docker (single-command deploy)

This builds the React frontend, bundles it into the FastAPI image, and starts Postgres + the API/UI together.

From repo root:

```bash
docker compose -f infra/compose.yaml up --build
```

Then run migrations in the API container (first run, or after new migrations):

```bash
docker compose -f infra/compose.yaml exec api alembic upgrade head
```

This uses:
- Postgres on `5432`
- API + UI on `http://localhost:8000` (the built React app is served at `/`, the API under `/api/v1`, docs at `/docs`)

## Local development (two dev servers)

For day-to-day development you run the backend and frontend separately so both get fast reload.

### 1) Start Postgres

```bash
docker compose -f infra/compose.yaml up -d db
```

Wait until Postgres is healthy:

```bash
docker compose -f infra/compose.yaml logs db
```

Look for a line like `database system is ready to accept connections`.

### 2) Backend: install deps, migrate, run

```bash
cd backend
python3.11 -m venv .venv_local
source .venv_local/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/dev.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

If you get `fe_sendauth: no password supplied`, your `DATABASE_URL` in `.env` is missing credentials — set it to the value shown above.

If you see `ModuleNotFoundError` errors around app imports, make sure you're in `backend/` with the venv active.

The API is now on `http://localhost:8000` (`/docs` for the OpenAPI UI). `backend/app/static` is empty in this mode, so `/` will 404 — that's expected; use the frontend dev server below for the UI.

### 3) Frontend: install deps, run

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api/*` requests to `http://localhost:8000`, so the backend above must be running.

### Building the frontend into the backend for a local single-process check

If you want to sanity-check the bundled-single-process setup without Docker:

```bash
cd frontend
npm install
npm run build
rm -rf ../backend/app/static
cp -r dist ../backend/app/static
```

Then run the backend normally (`uvicorn app.main:app --port 8000`) and open `http://localhost:8000/`.

## Tests

Backend, from `backend/` with your venv active:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache PYTHONPATH=. python -m pytest -q
```

Frontend, from `frontend/`:

```bash
npm run build   # tsc -b && vite build — type-checks and production-builds
npm run lint
```

There is no frontend unit/component test suite yet (see limitations below).

## Current limitations

- no auth/permissions system yet
- no recurring availability support
- planning runs are still computed inline, on demand (only Google busy-time sync runs as a background job)
- Google integration is functional for demo/dev, but not hardened as production OAuth infra
- the automatic sync sweep assumes a single API process/replica; running multiple API instances would need a lock or an external scheduler to avoid duplicate sweeps
- no frontend automated test suite (build + lint only)
