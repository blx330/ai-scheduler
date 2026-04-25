# AI Scheduler Demo MVP

Minimal scheduling app with:

- FastAPI backend
- SQLAlchemy + Alembic persistence
- Deterministic scheduling engine
- Real Google Calendar OAuth
- Real busy-time sync from connected calendars
- Manual slot confirmation
- Real Google Calendar event creation
- Single-page frontend served directly by FastAPI

## What works

Happy-path demo flow:

1. Create app users in the UI
2. Connect each user to Google Calendar
3. Choose source calendars for busy-time sync
4. Choose the organizer write calendar
5. Create a scheduling request with:
   - title
   - required attendees
   - duration
   - must-schedule-before datetime
   - preferred weekdays
   - preferred time window
6. Sync busy intervals for connected attendees
7. Rank the top 3 feasible slots
8. Confirm one slot
9. Create the Google Calendar event

Notes:

- The old freeform parser still exists, but the demo flow uses structured preferences from the UI for stability.
- Required attendees are the only attendee type used in the UI.
- Busy-time sync uses real Google Calendar data.
- Event creation uses the organizer's selected write calendar.
- Candidate generation is restricted to 8:00 AM to 12:00 AM in the organizer timezone.
- 12:00 AM to 8:00 AM is a hard forbidden window and never produces candidates.

## Repo layout

- `backend/app/api`: HTTP routes and schemas
- `backend/app/application/services`: orchestration and Google Calendar flow
- `backend/app/domain`: scheduling logic and scoring
- `backend/app/infrastructure`: DB, config, parser, Google client
- `backend/app/static`: demo frontend

## Google Cloud setup

1. Open Google Cloud Console.
2. Create or choose a project.
3. Enable the Google Calendar API.
4. Configure the OAuth consent screen.
5. Create an OAuth Client ID for a Web application.
6. Add this authorized redirect URI:

```text
http://localhost:8000/api/v1/google/oauth/callback
```

7. Copy the client ID and client secret into `.env`.

If Google OAuth succeeds but busy sync returns a `403` from `/calendar/v3/freeBusy`, the usual cause is that the Google Calendar API is still disabled for the OAuth project. Enable it in Google Cloud Console and wait a few minutes for propagation before retrying.

## Environment

Create `.env` from the example:

```bash
cp .env.example .env
```

Required variables:

- `DATABASE_URL`
- `PARSER_MODE`
- `APP_BASE_URL`
- `FRONTEND_URL`
- `OAUTH_STATE_SECRET`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

For the demo, keep:

```text
PARSER_MODE=stub
APP_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:8000
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/google/oauth/callback
```

Google Calendar OAuth will not work unless all of these are set:

- `OAUTH_STATE_SECRET`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

If those values are missing, the UI will surface: `OAuth not configured - set env vars`.

## Local run

### 1. Start PostgreSQL

```bash
docker compose -f infra/compose.yaml up -d db
```

### 2. Install backend dependencies

```bash
cd backend
python3 -m venv .venv_local
source .venv_local/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/dev.txt
```

### 3. Run migrations

From the API container:

```bash
cd /Users/chas/Documents/ai scheduler
docker compose -f infra/compose.yaml run --rm api alembic upgrade head
```

Or locally from `backend/` with a host-reachable `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql+psycopg://localhost:5432/scheduler
# If your local Postgres requires an explicit role, use your local db user.
# Example on this machine:
# export DATABASE_URL=postgresql+psycopg://chas@localhost:5432/scheduler
alembic upgrade head
```

### 4. Run the app

```bash
cd backend
source .venv_local/bin/activate
export DATABASE_URL=postgresql+psycopg://localhost:5432/scheduler
# If your local Postgres requires an explicit role, use your local db user.
# Example on this machine:
# export DATABASE_URL=postgresql+psycopg://chas@localhost:5432/scheduler
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://localhost:8000/
```

There is no separate frontend server.

## Docker run

If you want to run the API inside Docker:

```bash
docker compose -f infra/compose.yaml up --build
```

The UI is still served from:

```text
http://localhost:8000/
```

## Tests

Run the full backend suite:

```bash
cd backend
source .venv_local/bin/activate
PYTHONPYCACHEPREFIX=/tmp/pycache PYTHONPATH=. python -m pytest -q
```

## Demo checklist

1. Create at least two users with real email addresses.
2. Click `Connect Google Calendar` on each member card and finish the OAuth flow.
3. Click `Refresh calendars` and save the source/write calendar choices.
4. Pick an organizer.
5. Check required attendees.
6. Enter title, duration, deadline, preferred weekdays, and preferred hours.
7. Click `Find top 3 slots`.
8. Click `Confirm and create event` on one result.
9. Open the returned Google Calendar event link.

## Current scope limits

- No authentication system beyond user records in the demo
- No recurring availability
- No production token encryption/hardening
- No same-title minimum-gap rule yet
- No background jobs; sync happens inline during the demo flow
