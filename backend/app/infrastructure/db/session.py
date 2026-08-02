from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def build_session_factory(database_url: str) -> sessionmaker:
    engine_kwargs = {"future": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **engine_kwargs)
    if database_url.startswith("sqlite"):
        # SQLite ships with foreign key enforcement off, which silently turns every
        # ondelete="CASCADE"/"SET NULL" in the schema into a no-op. Postgres enforces
        # them, so without this the two backends disagree on delete behavior.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
