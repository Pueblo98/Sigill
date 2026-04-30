from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sigil.config import config
import logging
import asyncio

logger = logging.getLogger(__name__)

FALLBACK_URL = "sqlite+aiosqlite:///./sigil_dev.db"

engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def init_db():
    global engine, AsyncSessionLocal
    try:
        # Test primary connection (Postgres)
        async with engine.begin() as conn:
            pass
        logger.info(f"Connected to live Postgres: {config.DATABASE_URL.split('@')[-1]}")
    except Exception as e:
        logger.warning(f"Failed connecting to Postgres. Falling back to local SQLite: {FALLBACK_URL}")
        engine = create_async_engine(FALLBACK_URL, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    # Initialize all models (creates schema if it doesn't exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schemas verified.")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
