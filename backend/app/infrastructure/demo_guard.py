"""Abuse guardrails for the public shared demo deployment.

Both the rate limiter and the row cap are no-ops unless ADMIN_RESET_TOKEN is set
(the same signal that gates the admin reset endpoint) -- local dev, tests, and any
non-demo deployment are completely unaffected. This is deliberately blunt: it does
not stop one visitor from editing another's data (there's no auth for that), only
bounds how much a bot or a bad actor can spam between scheduled demo resets. State
is in-memory, matching the app's existing single-process assumption.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from sqlalchemy import func, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.infrastructure.db.models import DanceEvent, ManualAvailabilityInterval, User

DEMO_ROW_LIMIT = 400
RATE_LIMIT_MAX_REQUESTS = 30
RATE_LIMIT_WINDOW_SECONDS = 60.0

_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float) -> bool:
        hits = self._hits[key]
        cutoff = now - self._window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self._max_requests:
            return False
        hits.append(now)
        return True


class DemoGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limiter: SlidingWindowRateLimiter | None = None) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
        )

    async def dispatch(self, request: Request, call_next):
        settings = request.app.state.settings
        if not settings.admin_reset_token or request.method not in _MUTATING_METHODS:
            return await call_next(request)

        path = request.url.path
        if path.endswith("/admin/reset-demo"):
            # Trusted: only the scheduled reset job (bearing the admin token) calls this.
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if not self._rate_limiter.allow(client_ip, time.monotonic()):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests -- this is a shared public demo. Please slow down."},
            )

        if request.method == "POST" and "/google/" not in path:
            session_factory = request.app.state.session_factory
            with session_factory() as db:
                total_rows = sum(
                    db.scalar(select(func.count()).select_from(model)) or 0
                    for model in (User, DanceEvent, ManualAvailabilityInterval)
                )
            if total_rows >= DEMO_ROW_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Demo capacity reached -- resets every few hours. Try again soon."},
                )

        return await call_next(request)
