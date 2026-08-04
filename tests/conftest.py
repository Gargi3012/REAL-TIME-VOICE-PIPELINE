

from __future__ import annotations

import sys
import os
from typing import Generator

import pytest
from loguru import logger

os.environ["ENABLE_INITIAL_GREETING"] = "False"

from app.session import SessionManager, Session
import pytest_asyncio


# ──────────────────────────────────────────────────────────────────────
# Loguru capture fixture
# ──────────────────────────────────────────────────────────────────────

class LogCapture:
    """Collects Loguru log records in-memory for test assertions."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def sink(self, message) -> None:  # noqa: ANN001
        self.records.append(message.record)

    def messages(self) -> list[str]:
        return [r["message"] for r in self.records]

    def has_message_containing(self, substr: str) -> bool:
        return any(substr in m for m in self.messages())

    def count_level(self, level: str) -> int:
        return sum(1 for r in self.records if r["level"].name == level)

    def clear(self) -> None:
        self.records.clear()


@pytest.fixture()
def log_capture() -> Generator[LogCapture, None, None]:
    """Provide an in-memory Loguru sink and restore defaults after the test."""
    capture = LogCapture()
    logger.remove()
    handler_id = logger.add(capture.sink, level="DEBUG", format="{message}")
    yield capture
    logger.remove(handler_id)
    # Restore default stderr handler
    logger.add(sys.stderr, level="DEBUG")


# ──────────────────────────────────────────────────────────────────────
# Core fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture()
def manager(log_capture: LogCapture) -> SessionManager:
    """Return a fresh, empty SessionManager with logging captured."""
    mgr = SessionManager()
    log_capture.clear()  # discard init log so tests start clean
    return mgr



@pytest_asyncio.fixture()
async def session(manager: SessionManager) -> Session:
    """Return a pre-created session attached to the fixture manager."""
    return await manager.create_session(metadata={"env": "test"})


@pytest_asyncio.fixture()
async def populated_session(manager: SessionManager, session: Session) -> Session:
    """Return a session pre-loaded with three messages (one per role)."""
    await manager.add_message(session.session_id, "system", "You are a test bot.")
    await manager.add_message(session.session_id, "user", "Hello!")
    await manager.add_message(session.session_id, "assistant", "Hi there!")
    return session

# ──────────────────────────────────────────────────────────────────────
# Persistence (Database) fixtures
# ──────────────────────────────────────────────────────────────────────
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture(autouse=True)
def mock_pipecat_runners():
    """Autouse fixture to mock PipelineRunner.run and WorkerRunner.run in all tests."""
    from unittest.mock import patch
    try:
        with patch("pipecat.pipeline.runner.PipelineRunner.run") as r1, \
             patch("pipecat.pipeline.runner.WorkerRunner.run", create=True) as r2:
            yield r1, r2
    except Exception:
        yield None

