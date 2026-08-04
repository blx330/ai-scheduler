"""CLI entrypoint for the demo seed/reset logic in app.application.services.demo_seed_service.

Run with: python -m scripts.seed_demo
"""

from app.application.services.demo_seed_service import reset_demo
from app.infrastructure.config import Settings
from app.infrastructure.db.session import build_session_factory

if __name__ == "__main__":
    settings = Settings()
    session_factory = build_session_factory(settings.database_url)
    with session_factory() as session:
        reset_demo(session)
    print("Demo data reset and reseeded.")
