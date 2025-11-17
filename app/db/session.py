"""
Database Session Management
Handles database connections and session lifecycle
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine
)
import structlog

from app.config.settings import settings

logger = structlog.get_logger()

# Core database engine
core_engine: AsyncEngine | None = None
core_session_factory: async_sessionmaker[AsyncSession] | None = None

# Ingest database engine (read-only)
ingest_engine: AsyncEngine | None = None
ingest_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db():
    """Initialize database connections."""
    global core_engine, core_session_factory, ingest_engine, ingest_session_factory
    
    # Core database
    core_engine = create_async_engine(
        str(settings.database_url),
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_pre_ping=True,
        # poolclass is automatically selected for async engines
    )
    
    core_session_factory = async_sessionmaker(
        core_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Ingest database (read-only) - optional
    if settings.ingest_database_url:
        ingest_engine = create_async_engine(
            str(settings.ingest_database_url),
            echo=False,
            pool_size=settings.ingest_database_pool_size,
            pool_pre_ping=True,
            # poolclass is automatically selected for async engines
        )
        
        ingest_session_factory = async_sessionmaker(
            ingest_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Ingest database engine initialized")
    else:
        logger.warning("Ingest database URL not configured - sync features will be disabled")
    
    logger.info("Database engines initialized")


async def close_db():
    """Close database connections."""
    global core_engine, ingest_engine
    
    if core_engine:
        await core_engine.dispose()
        logger.info("Core database engine closed")
    
    if ingest_engine:
        await ingest_engine.dispose()
        logger.info("Ingest database engine closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get Core database session."""
    if not core_session_factory:
        raise RuntimeError("Database not initialized")
    
    async with core_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_ingest_session() -> AsyncGenerator[AsyncSession, None]:
    """Get Ingest database session (read-only)."""
    if not ingest_session_factory:
        raise RuntimeError(
            "Ingest database not configured. "
            "Please set INGEST_DATABASE_URL in .env to enable sync features."
        )
    
    async with ingest_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database dependency for FastAPI."""
    async with get_session() as session:
        yield session


async def get_ingest_db() -> AsyncGenerator[AsyncSession, None]:
    """Ingest database dependency for FastAPI."""
    async with get_ingest_session() as session:
        yield session
