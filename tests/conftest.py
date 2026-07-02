"""
Shared pytest fixtures for the session management test suite.

Design:
    Every test gets a fresh SessionManager and a pre-populated session so
    that tests are fully isolated and deterministic.  Loguru is reconfigured
    to capture log records in-memory for assertion without polluting stdout.
"""

from __future__ import annotations

import sys
from typing import Generator

import pytest
from loguru import logger

from app.session import SessionManager, Session, Message, SessionState


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


@pytest.fixture()
def session(manager: SessionManager) -> Session:
    """Return a pre-created session attached to the fixture manager."""
    return manager.create_session(metadata={"env": "test"})


@pytest.fixture()
def populated_session(manager: SessionManager, session: Session) -> Session:
    """Return a session pre-loaded with three messages (one per role)."""
    manager.add_message(session.session_id, "system", "You are a test bot.")
    manager.add_message(session.session_id, "user", "Hello!")
    manager.add_message(session.session_id, "assistant", "Hi there!")
    return session
