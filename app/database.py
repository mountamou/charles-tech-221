from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

is_sqlite = settings.database_url.startswith("sqlite")
kwargs = {"connect_args": {"check_same_thread": False}} if is_sqlite else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, **kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        # WAL is required by Litestream; busy_timeout rides out its brief checkpoint locks.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
