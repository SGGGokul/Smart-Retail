import logging
from typing import AsyncGenerator, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger("retailiq.db")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def normalize_database_url(url: str) -> str:
    """Ensure database URL specifies an async driver compatible with SQLAlchemy."""
    if not url:
        raise ValueError("DATABASE_URL must be a non-empty string.")

    # Convert standard postgresql:// to asyncpg driver
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


def get_engine() -> AsyncEngine:
    """Initialize or return the cached async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not configured. An explicit PostgreSQL database URL is required."
            )

        db_url = normalize_database_url(settings.DATABASE_URL)

        # SQLite testing support (e.g. sqlite+aiosqlite://) does not support pool_size
        if db_url.startswith("sqlite"):
            _engine = create_async_engine(
                db_url,
                echo=settings.DATABASE_ECHO,
            )
        elif "test" in db_url.lower():
            from sqlalchemy.pool import NullPool
            _engine = create_async_engine(
                db_url,
                echo=settings.DATABASE_ECHO,
                poolclass=NullPool,
            )
        else:
            _engine = create_async_engine(
                db_url,
                echo=settings.DATABASE_ECHO,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
        logger.info(f"Database engine initialized for driver: {_engine.dialect.name}")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Initialize or return the cached async sessionmaker."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an isolated async database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_connectivity() -> Tuple[bool, str]:
    """Test connection to the configured database.
    
    Returns (True, details) on success, or (False, error_reason) on failure.
    Never silently switches database engines.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            if scalar == 1:
                return True, f"Connected successfully to {engine.dialect.name} database."
            return False, f"Unexpected response from database: {scalar}"
    except Exception as exc:
        return False, f"Database connectivity check failed: {str(exc)}"


async def close_db_engine() -> None:
    """Dispose of the database engine on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine connections closed.")
