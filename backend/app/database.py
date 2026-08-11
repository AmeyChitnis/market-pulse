"""
SQLAlchemy engine and session setup.

Other modules import `Base` (to define models), `engine` (for startup
table creation), and `get_db` (as a FastAPI dependency for request-scoped
sessions). No other module should construct its own engine or session.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# check_same_thread=False is required for SQLite when used with FastAPI,
# since requests may be handled on a different thread than the one that
# created the connection. This is safe here because each request gets its
# own session via get_db().
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)

@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """SD-card friendly SQLite settings.

    WAL cuts write amplification, which matters on flash storage that
    wears out. synchronous=NORMAL skips an fsync per transaction — the
    documented risk is losing the last few transactions on power loss,
    which for a price logger that re-collects every 15 minutes is an
    acceptable trade against the card lasting years instead of months.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

