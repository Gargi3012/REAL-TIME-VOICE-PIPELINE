"""
Tests for app.session.manager — SessionManager CRUD + conversation ops.
"""

from __future__ import annotations

import pytest

from app.session import SessionManager, Session, Message, SessionState


class TestCreateSession:
    def test_returns_session(self, manager: SessionManager) -> None:
        s = manager.create_session()
        assert isinstance(s, Session)

    def test_increments_count(self, manager: SessionManager) -> None:
        manager.create_session()
        manager.create_session()
        assert manager.total_sessions() == 2

    def test_with_metadata(self, manager: SessionManager) -> None:
        s = manager.create_session(metadata={"user": "rahul"})
        assert s.metadata == {"user": "rahul"}

    def test_without_metadata(self, manager: SessionManager) -> None:
        s = manager.create_session()
        assert s.metadata == {}

    def test_default_state_idle(self, manager: SessionManager) -> None:
        assert manager.create_session().current_state == SessionState.IDLE


class TestGetSession:
    def test_existing(self, manager: SessionManager, session: Session) -> None:
        assert manager.get_session(session.session_id) is session

    def test_nonexistent(self, manager: SessionManager) -> None:
        assert manager.get_session("nonexistent") is None


class TestDeleteSession:
    def test_delete_existing(self, manager: SessionManager, session: Session) -> None:
        assert manager.delete_session(session.session_id) is True
        assert manager.total_sessions() == 0

    def test_delete_marks_closed(self, manager: SessionManager) -> None:
        s = manager.create_session()
        manager.delete_session(s.session_id)
        assert s.current_state == SessionState.CLOSED

    def test_delete_nonexistent(self, manager: SessionManager) -> None:
        assert manager.delete_session("bogus") is False

    def test_double_delete(self, manager: SessionManager, session: Session) -> None:
        manager.delete_session(session.session_id)
        assert manager.delete_session(session.session_id) is False

    def test_get_after_delete(self, manager: SessionManager, session: Session) -> None:
        manager.delete_session(session.session_id)
        assert manager.get_session(session.session_id) is None


class TestListSessions:
    def test_empty(self, manager: SessionManager) -> None:
        assert manager.list_sessions() == []

    def test_multiple(self, manager: SessionManager) -> None:
        manager.create_session()
        manager.create_session()
        assert len(manager.list_sessions()) == 2

    def test_returns_copy(self, manager: SessionManager) -> None:
        manager.create_session()
        l1 = manager.list_sessions()
        l2 = manager.list_sessions()
        assert l1 is not l2


class TestSessionExists:
    def test_exists(self, manager: SessionManager, session: Session) -> None:
        assert manager.session_exists(session.session_id) is True

    def test_not_exists(self, manager: SessionManager) -> None:
        assert manager.session_exists("nope") is False


class TestTotalSessions:
    def test_empty(self, manager: SessionManager) -> None:
        assert manager.total_sessions() == 0

    def test_after_creates_and_deletes(self, manager: SessionManager) -> None:
        s1 = manager.create_session()
        manager.create_session()
        manager.delete_session(s1.session_id)
        assert manager.total_sessions() == 1


class TestAddMessage:
    def test_returns_message(self, manager: SessionManager, session: Session) -> None:
        m = manager.add_message(session.session_id, "user", "hi")
        assert isinstance(m, Message)
        assert m.role == "user" and m.content == "hi"

    def test_appends_to_history(self, manager: SessionManager, session: Session) -> None:
        manager.add_message(session.session_id, "user", "hello")
        assert len(session.history) == 1

    def test_nonexistent_session(self, manager: SessionManager) -> None:
        assert manager.add_message("bad-id", "user", "hi") is None

    def test_invalid_role_raises(self, manager: SessionManager, session: Session) -> None:
        with pytest.raises(ValueError):
            manager.add_message(session.session_id, "admin", "hi")  # type: ignore

    def test_empty_content_raises(self, manager: SessionManager, session: Session) -> None:
        with pytest.raises(ValueError):
            manager.add_message(session.session_id, "user", "")

    def test_updates_last_activity(self, manager: SessionManager, session: Session) -> None:
        old = session.last_activity
        import time; time.sleep(0.01)
        manager.add_message(session.session_id, "user", "hi")
        assert session.last_activity > old


class TestGetHistory:
    def test_empty(self, manager: SessionManager, session: Session) -> None:
        assert manager.get_history(session.session_id) == []

    def test_with_messages(self, manager: SessionManager, populated_session: Session) -> None:
        h = manager.get_history(populated_session.session_id)
        assert h is not None and len(h) == 3

    def test_returns_copy(self, manager: SessionManager, session: Session) -> None:
        manager.add_message(session.session_id, "user", "hi")
        h1 = manager.get_history(session.session_id)
        h2 = manager.get_history(session.session_id)
        assert h1 is not h2

    def test_nonexistent(self, manager: SessionManager) -> None:
        assert manager.get_history("nope") is None


class TestClearHistory:
    def test_clears(self, manager: SessionManager, populated_session: Session) -> None:
        assert manager.clear_history(populated_session.session_id) is True
        assert manager.get_history(populated_session.session_id) == []

    def test_nonexistent(self, manager: SessionManager) -> None:
        assert manager.clear_history("nope") is False

    def test_double_clear(self, manager: SessionManager, session: Session) -> None:
        manager.add_message(session.session_id, "user", "hi")
        manager.clear_history(session.session_id)
        assert manager.clear_history(session.session_id) is True  # no-op but valid


class TestUpdateLastActivity:
    def test_updates(self, manager: SessionManager, session: Session) -> None:
        old = session.last_activity
        import time; time.sleep(0.01)
        assert manager.update_last_activity(session.session_id) is True
        assert session.last_activity > old

    def test_nonexistent(self, manager: SessionManager) -> None:
        assert manager.update_last_activity("nope") is False


class TestSetState:
    def test_transition(self, manager: SessionManager, session: Session) -> None:
        assert manager.set_state(session.session_id, SessionState.LISTENING) is True
        assert session.current_state == SessionState.LISTENING

    def test_full_cycle(self, manager: SessionManager, session: Session) -> None:
        for state in [SessionState.LISTENING, SessionState.THINKING,
                      SessionState.SPEAKING, SessionState.IDLE]:
            assert manager.set_state(session.session_id, state) is True
        assert session.current_state == SessionState.IDLE

    def test_interrupted_flow(self, manager: SessionManager, session: Session) -> None:
        manager.set_state(session.session_id, SessionState.SPEAKING)
        manager.set_state(session.session_id, SessionState.INTERRUPTED)
        assert session.current_state == SessionState.INTERRUPTED

    def test_closed_blocks_transitions(self, manager: SessionManager, session: Session) -> None:
        manager.set_state(session.session_id, SessionState.CLOSED)
        assert manager.set_state(session.session_id, SessionState.IDLE) is False

    def test_nonexistent(self, manager: SessionManager) -> None:
        assert manager.set_state("nope", SessionState.IDLE) is False


class TestDunders:
    def test_repr(self, manager: SessionManager) -> None:
        assert "active_sessions=0" in repr(manager)

    def test_len(self, manager: SessionManager) -> None:
        assert len(manager) == 0
        manager.create_session()
        assert len(manager) == 1
