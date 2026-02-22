import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Engine and session factory are created lazily on first request
# so that importing the module doesn't fail when DATABASE_URL is not set.
_engine = None
_session_factory = None


def _get_url() -> str:
    """Build asyncpg URL from DATABASE_URL env var (Railway provides postgresql://)."""
    raw = os.environ["DATABASE_URL"]
    return raw.replace("postgresql://", "postgresql+asyncpg://", 1)


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(_get_url(), echo=False, pool_pre_ping=True)
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session."""
    async with _get_session_factory()() as session:
        yield session
