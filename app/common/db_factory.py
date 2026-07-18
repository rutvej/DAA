import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_unified_engine(
    database_url: str = None, pool_size: int = 20, max_overflow: int = 40
):
    """
    Creates a unified SQLAlchemy engine with standardized pooling and resilience settings:
    - pool_pre_ping=True: Verifies connections before check-out, preventing InterfaceErrors when DB restarts.
    - pool_recycle=3600: Recycles stale connections every hour.
    - Standardized timeouts across SQLite and PostgreSQL.
    """
    if not database_url:
        database_url = os.environ.get("DATABASE_URL", "sqlite:///./daa.db")

    is_sqlite = "sqlite" in database_url.lower()

    if is_sqlite:
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": 30.0},
            pool_timeout=30,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    else:
        return create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=60,
            pool_pre_ping=True,
            pool_recycle=3600,
        )


def get_session_maker(engine):
    """
    Returns a standardized SQLAlchemy sessionmaker bound to the unified engine.
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
