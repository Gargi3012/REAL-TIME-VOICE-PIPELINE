"""
Tests for app.session.state — SessionState enum.

Covers:
    - All enum members exist with correct values
    - is_active() returns True only for processing states
    - is_terminal() returns True only for CLOSED
    - Enum iteration, identity, and string serialization
"""

from __future__ import annotations

import pytest

from app.session.state import SessionState


# ──────────────────────────────────────────────────────────────
# Enum membership
# ──────────────────────────────────────────────────────────────

class TestSessionStateMembers:
    """Verify all 6 states exist with the correct string values."""

    EXPECTED_MEMBERS = {
        "IDLE": "idle",
        "LISTENING": "listening",
        "THINKING": "thinking",
        "SPEAKING": "speaking",
        "INTERRUPTED": "interrupted",
        "CLOSED": "closed",
    }

    def test_member_count(self) -> None:
        assert len(SessionState) == 6

    @pytest.mark.parametrize("name,value", EXPECTED_MEMBERS.items())
    def test_member_value(self, name: str, value: str) -> None:
        member = SessionState[name]
        assert member.value == value

    def test_construction_from_value(self) -> None:
        assert SessionState("idle") is SessionState.IDLE

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            SessionState("running")


# ──────────────────────────────────────────────────────────────
# is_active()
# ──────────────────────────────────────────────────────────────

class TestIsActive:
    """is_active() should be True for LISTENING, THINKING, SPEAKING only."""

    @pytest.mark.parametrize("state", [
        SessionState.LISTENING,
        SessionState.THINKING,
        SessionState.SPEAKING,
    ])
    def test_active_states(self, state: SessionState) -> None:
        assert state.is_active() is True

    @pytest.mark.parametrize("state", [
        SessionState.IDLE,
        SessionState.INTERRUPTED,
        SessionState.CLOSED,
    ])
    def test_inactive_states(self, state: SessionState) -> None:
        assert state.is_active() is False


# ──────────────────────────────────────────────────────────────
# is_terminal()
# ──────────────────────────────────────────────────────────────

class TestIsTerminal:
    """is_terminal() should be True only for CLOSED."""

    def test_closed_is_terminal(self) -> None:
        assert SessionState.CLOSED.is_terminal() is True

    @pytest.mark.parametrize("state", [
        SessionState.IDLE,
        SessionState.LISTENING,
        SessionState.THINKING,
        SessionState.SPEAKING,
        SessionState.INTERRUPTED,
    ])
    def test_non_terminal_states(self, state: SessionState) -> None:
        assert state.is_terminal() is False


# ──────────────────────────────────────────────────────────────
# Identity / comparison
# ──────────────────────────────────────────────────────────────

class TestIdentity:

    def test_enum_identity(self) -> None:
        assert SessionState.IDLE is SessionState.IDLE

    def test_enum_equality(self) -> None:
        assert SessionState.IDLE == SessionState("idle")

    def test_enum_not_equal_to_string(self) -> None:
        assert SessionState.IDLE != "idle"

    def test_iteration(self) -> None:
        states = list(SessionState)
        assert len(states) == 6
        assert all(isinstance(s, SessionState) for s in states)

    def test_hashable(self) -> None:
        """Enums must be hashable for use as dict keys / set members."""
        state_set = {SessionState.IDLE, SessionState.CLOSED}
        assert len(state_set) == 2
