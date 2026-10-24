from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def create_database_engine(database_url: str | None = None):
    url = database_url or settings.database_url
    if not url:
        raise RuntimeError("DATABASE_URL must be set before connecting to PostgreSQL")

    engine = create_engine(url, pool_pre_ping=True)

    if engine.dialect.name == "postgresql":
        @event.listens_for(engine, "connect")
        def set_pacific_timezone(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("SET TIME ZONE 'America/Los_Angeles'")
            cursor.close()

    return engine


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_database_engine(database_url),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    session_factory = create_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
