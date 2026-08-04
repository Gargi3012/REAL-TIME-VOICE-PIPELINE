"""
Asynchronous concurrency safety stress tests for SessionManager.

Spawns multiple concurrent async tasks performing CRUD + message operations
and verifies no crashes, corrupted state, or data loss.
"""

from __future__ import annotations

import asyncio
import pytest

from app.session import SessionManager, SessionState


class TestConcurrentCreation:
    """Multiple concurrent tasks creating sessions simultaneously."""

    @pytest.mark.asyncio
    async def test_100_concurrent_creates(self, manager: SessionManager) -> None:
        errors: list[Exception] = []

        async def create() -> None:
            try:
                await manager.create_session()
            except Exception as e:
                errors.append(e)

        await asyncio.gather(*(create() for _ in range(100)))

        assert not errors
        assert (await manager.total_sessions()) == 100


class TestConcurrentCreateDelete:
    """Concurrent tasks creating and deleting sessions simultaneously."""

    @pytest.mark.asyncio
    async def test_create_and_delete(self, manager: SessionManager) -> None:
        # Pre-create sessions to delete
        ids = []
        for _ in range(50):
            s = await manager.create_session()
            ids.append(s.session_id)
            
        errors: list[Exception] = []

        async def create_batch() -> None:
            try:
                for _ in range(50):
                    await manager.create_session()
            except Exception as e:
                errors.append(e)

        async def delete_batch() -> None:
            try:
                for sid in ids:
                    await manager.delete_session(sid)
            except Exception as e:
                errors.append(e)

        await asyncio.gather(create_batch(), delete_batch())

        assert not errors
        # 50 original deleted + 50 new created = 50 remaining
        assert (await manager.total_sessions()) == 50


class TestConcurrentMessages:
    """Multiple concurrent tasks adding messages to the same session."""

    @pytest.mark.asyncio
    async def test_concurrent_message_adds(self, manager: SessionManager) -> None:
        session = await manager.create_session()
        sid = session.session_id
        n_tasks = 10
        n_msgs = 50
        errors: list[Exception] = []

        async def add_messages(task_id: int) -> None:
            try:
                for i in range(n_msgs):
                    await manager.add_message(sid, "user", f"t{task_id}-m{i}")
            except Exception as e:
                errors.append(e)

        await asyncio.gather(*(add_messages(i) for i in range(n_tasks)))

        assert not errors
        history = await manager.get_history(sid)
        assert history is not None
        assert len(history) == n_tasks * n_msgs


class TestConcurrentMixedOps:
    """Tasks performing concurrent reads, writes, deletes, and state changes."""

    @pytest.mark.asyncio
    async def test_mixed_operations(self, manager: SessionManager) -> None:
        sessions = []
        for _ in range(20):
            s = await manager.create_session()
            sessions.append(s)
            
        errors: list[Exception] = []

        async def reader() -> None:
            try:
                for s in sessions:
                    await manager.get_session(s.session_id)
                    await manager.get_history(s.session_id)
                    await manager.session_exists(s.session_id)
            except Exception as e:
                errors.append(e)

        async def writer() -> None:
            try:
                for s in sessions:
                    await manager.add_message(s.session_id, "user", "concurrent")
                    await manager.update_last_activity(s.session_id)
            except Exception as e:
                errors.append(e)

        async def state_changer() -> None:
            try:
                for s in sessions:
                    await manager.set_state(s.session_id, SessionState.LISTENING)
                    await manager.set_state(s.session_id, SessionState.IDLE)
            except Exception as e:
                errors.append(e)

        # Mix of readers, writers, and state changers
        tasks = (
            [reader() for _ in range(3)]
            + [writer() for _ in range(3)]
            + [state_changer() for _ in range(2)]
        )
        await asyncio.gather(*tasks)

        assert not errors
