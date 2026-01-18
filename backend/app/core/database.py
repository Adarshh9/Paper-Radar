"""
Database connection and session management.
Supports both PostgreSQL (production) and SQLite (local development).
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import get_settings

settings = get_settings()

# Determine which database to use
database_url = settings.effective_database_url

# Configure engine based on database type
if settings.use_local_storage:
    # SQLite configuration
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
        pool_pre_ping=True,
    )
    
    # Enable foreign keys for SQLite (disabled by default)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL configuration
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """
    Initialize the database by creating all tables.
    Call this at application startup for local development.
    """
    # Import all models to ensure they're registered with Base
    from app.models import (  # noqa: F401
        Paper, PaperMetrics, PaperImplementation, PaperSummary, PaperRelationship,
        User, UserPreferences, UserInteraction,
    )
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency that provides a database session.
    Ensures session is closed after request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
