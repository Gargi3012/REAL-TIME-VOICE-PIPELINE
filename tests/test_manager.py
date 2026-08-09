"""
Tests for app.session.manager — SessionManager CRUD + conversation ops.
"""

from __future__ import annotations

import pytest

from app.session import SessionManager, Session, Message, SessionState


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_returns_session(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        assert isinstance(s, Session)

    @pytest.mark.asyncio
    async def test_increments_count(self, manager: SessionManager) -> None:
        await manager.create_session()
        await manager.create_session()
        assert (await manager.total_sessions()) == 2

    @pytest.mark.asyncio
    async def test_with_metadata(self, manager: SessionManager) -> None:
        s = await manager.create_session(metadata={"user": "rahul"})
        assert s.metadata == {"user": "rahul"}

    @pytest.mark.asyncio
    async def test_without_metadata(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        assert s.metadata == {}

    @pytest.mark.asyncio
    async def test_default_state_idle(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        assert s.current_state == SessionState.IDLE


class TestGetSession:
    @pytest.mark.asyncio
    async def test_existing(self, manager: SessionManager, session: Session) -> None:
        assert (await manager.get_session(session.session_id)) is session

    @pytest.mark.asyncio
    async def test_nonexistent(self, manager: SessionManager) -> None:
        assert (await manager.get_session("nonexistent")) is None


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_existing(self, manager: SessionManager, session: Session) -> None:
        assert (await manager.delete_session(session.session_id)) is True
        assert (await manager.total_sessions()) == 0

    @pytest.mark.asyncio
    async def test_delete_marks_closed(self, manager: SessionManager) -> None:
        s = await manager.create_session()
        await manager.delete_session(s.session_id)
        assert s.current_state == SessionState.CLOSED

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, manager: SessionManager) -> None:
        assert (await manager.delete_session("bogus")) is False

    @pytest.mark.asyncio
    async def test_double_delete(self, manager: SessionManager, session: Session) -> None:
        await manager.delete_session(session.session_id)
        assert (await manager.delete_session(session.session_id)) is False

    @pytest.mark.asyncio
    async def test_get_after_delete(self, manager: SessionManager, session: Session) -> None:
        await manager.delete_session(session.session_id)
        assert (await manager.get_session(session.session_id)) is None


class TestListSessions:
    @pytest.mark.asyncio
    async def test_empty(self, manager: SessionManager) -> None:
        assert (await manager.list_sessions()) == []

    @pytest.mark.asyncio
    async def test_multiple(self, manager: SessionManager) -> None:
        await manager.create_session()
        await manager.create_session()
        assert len(await manager.list_sessions()) == 2

    @pytest.mark.asyncio
    async def test_returns_copy(self, manager: SessionManager) -> None:
        await manager.create_session()
        l1 = await manager.list_sessions()
        l2 = await manager.list_sessions()
        assert l1 is not l2


class TestSessionExists:
    @pytest.mark.asyncio
    async def test_exists(self, manager: SessionManager, session: Session) -> None:
        assert (await manager.session_exists(session.session_id)) is True

    @pytest.mark.asyncio
    async def test_not_exists(self, manager: SessionManager) -> None:
        assert (await manager.session_exists("nope")) is False


class TestTotalSessions:
    @pytest.mark.asyncio
    async def test_empty(self, manager: SessionManager) -> None:
        assert (await manager.total_sessions()) == 0

    @pytest.mark.asyncio
    async def test_after_creates_and_deletes(self, manager: SessionManager) -> None:
        s1 = await manager.create_session()
        await manager.create_session()
        await manager.delete_session(s1.session_id)
        assert (await manager.total_sessions()) == 1


class TestAddMessage:
    @pytest.mark.asyncio
    async def test_returns_message(self, manager: SessionManager, session: Session) -> None:
        m = await manager.add_message(session.session_id, "user", "hi")
        assert isinstance(m, Message)
        assert m.role == "user" and m.content == "hi"

    @pytest.mark.asyncio
    async def test_appends_to_history(self, manager: SessionManager, session: Session) -> None:
        await manager.add_message(session.session_id, "user", "hello")
        assert len(session.history) == 1

    @pytest.mark.asyncio
    async def test_nonexistent_session(self, manager: SessionManager) -> None:
        assert (await manager.add_message("bad-id", "user", "hi")) is None

    @pytest.mark.asyncio
    async def test_invalid_role_raises(self, manager: SessionManager, session: Session) -> None:
        with pytest.raises(ValueError):
            await manager.add_message(session.session_id, "admin", "hi")  # type: ignore

    @pytest.mark.asyncio
    async def test_empty_content_raises(self, manager: SessionManager, session: Session) -> None:
        with pytest.raises(ValueError):
            await manager.add_message(session.session_id, "user", "")

    @pytest.mark.asyncio
    async def test_updates_last_activity(self, manager: SessionManager, session: Session) -> None:
        old = session.last_activity
        import time
        time.sleep(0.01)
        await manager.add_message(session.session_id, "user", "hi")
        assert session.last_activity > old


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_empty(self, manager: SessionManager, session: Session) -> None:
        assert (await manager.get_history(session.session_id)) == []

    @pytest.mark.asyncio
    async def test_with_messages(self, manager: SessionManager, populated_session: Session) -> None:
        h = await manager.get_history(populated_session.session_id)
        assert h is not None and len(h) == 3

    @pytest.mark.asyncio
    async def test_returns_copy(self, manager: SessionManager, session: Session) -> None:
        await manager.add_message(session.session_id, "user", "hi")
        h1 = await manager.get_history(session.session_id)
        h2 = await manager.get_history(session.session_id)
        assert h1 is not h2

    @pytest.mark.asyncio
    async def test_nonexistent(self, manager: SessionManager) -> None:
        assert (await manager.get_history("nope")) is None


class TestClearHistory:
    @pytest.mark.asyncio
    async def test_clears(self, manager: SessionManager, populated_session: Session) -> None:
        assert (await manager.clear_history(populated_session.session_id)) is True
        assert (await manager.get_history(populated_session.session_id)) == []

    @pytest.mark.asyncio
    async def test_nonexistent(self, manager: SessionManager) -> None:
        assert (await manager.clear_history("nope")) is False

    @pytest.mark.asyncio
    async def test_double_clear(self, manager: SessionManager, session: Session) -> None:
        await manager.add_message(session.session_id, "user", "hi")
        await manager.clear_history(session.session_id)
        assert (await manager.clear_history(session.session_id)) is True  # no-op but valid


class TestUpdateLastActivity:
    @pytest.mark.asyncio
    async def test_updates(self, manager: SessionManager, session: Session) -> None:
        old = session.last_activity
        import time
        time.sleep(0.01)
        assert (await manager.update_last_activity(session.session_id)) is True
        assert session.last_activity > old

    @pytest.mark.asyncio
    async def test_nonexistent(self, manager: SessionManager) -> None:
        assert (await manager.update_last_activity("nope")) is False


class TestSetState:
    @pytest.mark.asyncio
    async def test_transition(self, manager: SessionManager, session: Session) -> None:
        assert (await manager.set_state(session.session_id, SessionState.LISTENING)) is True
        assert session.current_state == SessionState.LISTENING

    @pytest.mark.asyncio
    async def test_full_cycle(self, manager: SessionManager, session: Session) -> None:
        for state in [SessionState.LISTENING, SessionState.THINKING,
                      SessionState.SPEAKING, SessionState.IDLE]:
            assert (await manager.set_state(session.session_id, state)) is True
        assert session.current_state == SessionState.IDLE

    @pytest.mark.asyncio
    async def test_interrupted_flow(self, manager: SessionManager, session: Session) -> None:
        await manager.set_state(session.session_id, SessionState.SPEAKING)
        await manager.set_state(session.session_id, SessionState.INTERRUPTED)
        assert session.current_state == SessionState.INTERRUPTED

    @pytest.mark.asyncio
    async def test_closed_blocks_transitions(self, manager: SessionManager, session: Session) -> None:
        await manager.set_state(session.session_id, SessionState.CLOSED)
        assert (await manager.set_state(session.session_id, SessionState.IDLE)) is False

    @pytest.mark.asyncio
    async def test_nonexistent(self, manager: SessionManager) -> None:
        assert (await manager.set_state("nope", SessionState.IDLE)) is False


class TestDunders:
    def test_repr(self, manager: SessionManager) -> None:
        assert "sessions_stored=0" in repr(manager)
