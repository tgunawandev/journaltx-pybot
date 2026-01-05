"""
Database session management.

Provides explicit ORM session handling with SQLAlchemy.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from journaltx.core.config import Config
from journaltx.core.models import Base


def get_engine(config: Config):
    """
    Create SQLAlchemy engine.

    Uses SQLite with WAL mode for better concurrency.
    """
    db_path = Path(config.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    # Enable WAL mode for better concurrent access
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()

    return engine


def init_db(config: Config) -> None:
    """
    Initialize database schema.

    Creates all tables if they don't exist.
    """
    engine = get_engine(config)
    Base.metadata.create_all(engine)


def get_session(config: Config) -> Session:
    """
    Create a new database session.

    Remember to close or use as context manager.
    """
    engine = get_engine(config)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@contextmanager
def session_scope(config: Config) -> Generator[Session, None, None]:
    """
    Provide transactional scope around a series of operations.

    Usage:
        with session_scope(config) as session:
            session.add(trade)
    """
    session = get_session(config)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
