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


async def init_db():
    """Initialize database connections."""
    global core_engine, core_session_factory
    
    # Core database
    core_engine = create_async_engine(
        str(settings.database_url),
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_pre_ping=True,
    )
    
    core_session_factory = async_sessionmaker(
        core_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    logger.info("Database engine initialized")


async def close_db():
    """Close database connections."""
    global core_engine
    
    if core_engine:
        await core_engine.dispose()
        logger.info("Database engine closed")


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


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database dependency for FastAPI."""
    async with get_session() as session:
        yield session
