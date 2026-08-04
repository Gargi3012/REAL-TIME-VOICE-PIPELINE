"""
Edge case tests for the session management layer.
"""

from __future__ import annotations

import pytest

from app.session import SessionManager, SessionState


class TestInvalidSessionIds:
    """Operations on non-existent, empty, and None session IDs."""

    @pytest.mark.parametrize("bad_id", ["", "   ", "nonexistent-uuid", "12345"])
    @pytest.mark.asyncio
    async def test_get(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.get_session(bad_id)) is None

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_delete(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.delete_session(bad_id)) is False

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_add_message(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.add_message(bad_id, "user", "test")) is None

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_get_history(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.get_history(bad_id)) is None

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_clear_history(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.clear_history(bad_id)) is False

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_update_activity(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.update_last_activity(bad_id)) is False

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_set_state(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.set_state(bad_id, SessionState.IDLE)) is False

    @pytest.mark.parametrize("bad_id", ["", "nonexistent"])
    @pytest.mark.asyncio
    async def test_exists(self, manager: SessionManager, bad_id: str) -> None:
        assert (await manager.session_exists(bad_id)) is False


class TestPostDeletion:
    """All ops must fail gracefully after a session is deleted."""

    @pytest.mark.asyncio
    async def test_operations_after_delete(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        sid = s.session_id
        await manager.delete_session(sid)

        assert (await manager.get_session(sid)) is None
        assert (await manager.add_message(sid, "user", "hi")) is None
        assert (await manager.get_history(sid)) is None
        assert (await manager.clear_history(sid)) is False
        assert (await manager.update_last_activity(sid)) is False
        assert (await manager.set_state(sid, SessionState.IDLE)) is False
        assert (await manager.session_exists(sid)) is False


class TestSpecialContent:
    """Unicode, emoji, multiline, very long messages."""

    @pytest.mark.asyncio
    async def test_unicode(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        m = await manager.add_message(s.session_id, "user", "こんにちは 🌍")
        assert m is not None and m.content == "こんにちは 🌍"

    @pytest.mark.asyncio
    async def test_multiline(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        text = "line1\nline2\nline3"
        m = await manager.add_message(s.session_id, "user", text)
        assert m is not None and "\n" in m.content

    @pytest.mark.asyncio
    async def test_very_long_message(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        m = await manager.add_message(s.session_id, "user", "x" * 50_000)
        assert m is not None and len(m.content) == 50_000

    @pytest.mark.asyncio
    async def test_html_injection(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        m = await manager.add_message(s.session_id, "user", "<script>alert(1)</script>")
        assert m is not None and "<script>" in m.content


class TestBulkCRUD:
    """Create 100 sessions, verify retrieval and deletion."""

    @pytest.mark.asyncio
    async def test_bulk_create_and_delete(self, manager: SessionManager) -> None:
        ids = []
        for _ in range(100):
            s = await manager.create_session()
            ids.append(s.session_id)

        assert (await manager.total_sessions()) == 100

        # Delete every other session
        for sid in ids[::2]:
            assert (await manager.delete_session(sid)) is True
        assert (await manager.total_sessions()) == 50

        # Remaining sessions still accessible
        for sid in ids[1::2]:
            assert (await manager.session_exists(sid)) is True

        # Deleted sessions not accessible
        for sid in ids[::2]:
            assert (await manager.session_exists(sid)) is False


class TestHistoryOrdering:
    """Messages must be in insertion order."""

    @pytest.mark.asyncio
    async def test_order_preserved(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        contents = [f"msg-{i}" for i in range(20)]
        for c in contents:
            await manager.add_message(s.session_id, "user", c)
        history = await manager.get_history(s.session_id)
        assert [m.content for m in history] == contents

    @pytest.mark.asyncio
    async def test_timestamps_non_decreasing(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        for i in range(10):
            await manager.add_message(s.session_id, "user", f"msg-{i}")
        history = await manager.get_history(s.session_id)
        for i in range(1, len(history)):
            assert history[i].timestamp >= history[i - 1].timestamp
