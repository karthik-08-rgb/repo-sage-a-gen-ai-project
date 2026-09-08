import logging
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

# Configure connect_args based on DB dialect
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

# For SQLite, enforce foreign keys
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables and extensions."""
    try:
        if settings.DATABASE_URL.startswith("postgresql"):
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                logger.info("pgvector extension ensured.")
    except Exception as e:
        logger.warning(f"Could not initialize pgvector extension: {e}")

    # Import all models before create_all
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
