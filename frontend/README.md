# AI Scheduler — frontend

React + TypeScript SPA for the AI Scheduler backend, built with Vite, Tailwind CSS, and hand-built shadcn/ui components (Radix primitives + class-variance-authority + tailwind-merge).

See the repo root `README.md` for the full local-dev and Docker workflow. Quick reference:

```bash
npm install
npm run dev     # http://localhost:5173, proxies /api to http://localhost:8000
npm run build   # tsc -b && vite build -> dist/
npm run lint    # oxlint
```

`vite.config.ts` sets `base: "./"` so the production build's asset paths are relative — this lets FastAPI serve `dist/` as static files from any mount path (see `backend/Dockerfile`, which copies `dist/` into `backend/app/static`).

## Structure

- `src/api/` - typed fetch client (`client.ts`), endpoint paths (`endpoints.ts`), and TypeScript types mirroring the backend Pydantic schemas (`types.ts`)
- `src/hooks/` - one TanStack Query hook module per backend resource (users, availability, events, planning, calendar, google-calendar); mutations invalidate related queries and toast on error
- `src/pages/` - top-level routed views (Members, Member detail, Events, Event detail, Planning, Calendar)
- `src/components/` - feature components (`people/`, `events/`, `planning/`, `layout/`) plus shadcn primitives in `components/ui/`
- `src/lib/` - `cn()` class helper, IANA timezone list, local-time/ISO conversion helpers, the shared `QueryClient`

## Known simplifications

- Planning-run results live in local component state; re-running planning replaces them rather than being cached per run ID.
- No frontend automated test suite yet — `npm run build` (type-checking) and `npm run lint` are the current quality gates.
