import contextlib
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import (
    DATABASE_MAX_OVERFLOW,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_TIMEOUT,
    DATABASE_URL,
)


class DatabaseConnectionManager:
    """Manages the async SQLAlchemy engine and session lifecycle."""
    
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def init_db(self) -> None:
        """Initialize the async engine and session factory."""
        if self._engine is None:
           self._engine = create_async_engine(
             DATABASE_URL,
             pool_size=DATABASE_POOL_SIZE,
             max_overflow=DATABASE_MAX_OVERFLOW,
             pool_timeout=DATABASE_POOL_TIMEOUT,
             pool_pre_ping=True,
             pool_recycle=300,
             echo=False,
            )
        self._sessionmaker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

    async def close(self) -> None:
        """Dispose of the engine connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Provide a transactional scope around a series of operations."""
        if self._sessionmaker is None:
            self.init_db()
            
        assert self._sessionmaker is not None, "Database not initialized properly"
        
        async with self._sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Global connection manager instance
db_manager = DatabaseConnectionManager()
