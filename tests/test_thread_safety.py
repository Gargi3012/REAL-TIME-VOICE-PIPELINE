"""
Thread safety stress tests for SessionManager.

Spawns multiple threads performing concurrent CRUD + message operations
and verifies no crashes, corrupted state, or data loss.
"""

from __future__ import annotations

import threading
import time

import pytest

from app.session import SessionManager, SessionState


class TestConcurrentCreation:
    """Multiple threads creating sessions simultaneously."""

    def test_100_concurrent_creates(self, manager: SessionManager) -> None:
        errors: list[Exception] = []

        def create() -> None:
            try:
                manager.create_session()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert manager.total_sessions() == 100


class TestConcurrentCreateDelete:
    """Threads creating and deleting sessions simultaneously."""

    def test_create_and_delete(self, manager: SessionManager) -> None:
        # Pre-create sessions to delete
        ids = [manager.create_session().session_id for _ in range(50)]
        errors: list[Exception] = []

        def create_batch() -> None:
            try:
                for _ in range(50):
                    manager.create_session()
            except Exception as e:
                errors.append(e)

        def delete_batch() -> None:
            try:
                for sid in ids:
                    manager.delete_session(sid)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=create_batch)
        t2 = threading.Thread(target=delete_batch)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors
        # 50 original deleted + 50 new created = 50 remaining
        assert manager.total_sessions() == 50


class TestConcurrentMessages:
    """Multiple threads adding messages to the same session."""

    def test_concurrent_message_adds(self, manager: SessionManager) -> None:
        session = manager.create_session()
        sid = session.session_id
        n_threads = 10
        n_msgs = 50
        errors: list[Exception] = []

        def add_messages(thread_id: int) -> None:
            try:
                for i in range(n_msgs):
                    manager.add_message(sid, "user", f"t{thread_id}-m{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_messages, args=(i,))
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        history = manager.get_history(sid)
        assert history is not None
        assert len(history) == n_threads * n_msgs


class TestConcurrentMixedOps:
    """Threads performing reads, writes, deletes, and state changes."""

    def test_mixed_operations(self, manager: SessionManager) -> None:
        sessions = [manager.create_session() for _ in range(20)]
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for s in sessions:
                    manager.get_session(s.session_id)
                    manager.get_history(s.session_id)
                    manager.session_exists(s.session_id)
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                for s in sessions:
                    manager.add_message(s.session_id, "user", "concurrent")
                    manager.update_last_activity(s.session_id)
            except Exception as e:
                errors.append(e)

        def state_changer() -> None:
            try:
                for s in sessions:
                    manager.set_state(s.session_id, SessionState.LISTENING)
                    manager.set_state(s.session_id, SessionState.IDLE)
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=reader) for _ in range(3)]
            + [threading.Thread(target=writer) for _ in range(3)]
            + [threading.Thread(target=state_changer) for _ in range(2)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
