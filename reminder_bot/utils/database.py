import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from ..models.entities import Base
from ..utils.logging import get_logger

logger = get_logger()

if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "").replace(
        "sqlite:///", ""
    )
    if db_path and not db_path.startswith(":"):
        parent_dir = os.path.dirname(db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            logger.info("Created SQLite database directory", directory=parent_dir)

engine = create_async_engine(
    settings.database_url, echo=settings.debug, pool_pre_ping=True, pool_recycle=3600
)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

_tables_initialized = False


async def _init_tables() -> None:
    """Initialize database tables on first use."""
    global _tables_initialized
    if not _tables_initialized:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _tables_initialized = True
        logger.info("Database tables initialized")


@asynccontextmanager
async def get_async_session():
    await _init_tables()
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
