"""
Tests for conversation transitions, validators, and ConversationState enum.
"""

from __future__ import annotations

import pytest

from app.conversation import (
    ConversationState,
    TRANSITION_MAP,
    get_allowed_transitions,
    can_transition,
    validate_transition,
    InvalidTransitionError,
    TerminalStateError,
)


# ──────────────────────────────────────────────────────────────
# Enum
# ──────────────────────────────────────────────────────────────

class TestConversationState:
    def test_member_count(self) -> None:
        assert len(ConversationState) == 10

    @pytest.mark.parametrize("name,value", [
        ("IDLE", "idle"), ("LISTENING", "listening"),
        ("TRANSCRIBING", "transcribing"), ("THINKING", "thinking"),
        ("GENERATING_RESPONSE", "generating_response"),
        ("GENERATING_AUDIO", "generating_audio"),
        ("SPEAKING", "speaking"), ("INTERRUPTED", "interrupted"),
        ("ERROR", "error"), ("CLOSED", "closed"),
    ])
    def test_values(self, name: str, value: str) -> None:
        assert ConversationState[name].value == value

    def test_is_terminal(self) -> None:
        assert ConversationState.CLOSED.is_terminal() is True
        assert ConversationState.IDLE.is_terminal() is False

    def test_is_error(self) -> None:
        assert ConversationState.ERROR.is_error() is True
        assert ConversationState.IDLE.is_error() is False

    @pytest.mark.parametrize("state", [
        ConversationState.LISTENING, ConversationState.TRANSCRIBING,
        ConversationState.THINKING, ConversationState.GENERATING_RESPONSE,
        ConversationState.GENERATING_AUDIO, ConversationState.SPEAKING,
    ])
    def test_is_processing_true(self, state: ConversationState) -> None:
        assert state.is_processing() is True

    @pytest.mark.parametrize("state", [
        ConversationState.IDLE, ConversationState.INTERRUPTED,
        ConversationState.ERROR, ConversationState.CLOSED,
    ])
    def test_is_processing_false(self, state: ConversationState) -> None:
        assert state.is_processing() is False


# ──────────────────────────────────────────────────────────────
# Transition map completeness
# ──────────────────────────────────────────────────────────────

class TestTransitionMap:
    def test_all_states_in_map(self) -> None:
        for state in ConversationState:
            assert state in TRANSITION_MAP

    def test_closed_has_no_outgoing(self) -> None:
        assert TRANSITION_MAP[ConversationState.CLOSED] == frozenset()

    def test_every_non_terminal_can_reach_closed(self) -> None:
        for state in ConversationState:
            if state is not ConversationState.CLOSED:
                assert ConversationState.CLOSED in TRANSITION_MAP[state]

    def test_error_only_to_idle_or_closed(self) -> None:
        allowed = TRANSITION_MAP[ConversationState.ERROR]
        assert allowed == frozenset({
            ConversationState.IDLE, ConversationState.CLOSED,
        })

    def test_interrupted_only_to_listening_or_closed(self) -> None:
        allowed = TRANSITION_MAP[ConversationState.INTERRUPTED]
        assert allowed == frozenset({
            ConversationState.LISTENING, ConversationState.CLOSED,
        })

    def test_get_allowed_transitions(self) -> None:
        r = get_allowed_transitions(ConversationState.IDLE)
        assert ConversationState.LISTENING in r


# ──────────────────────────────────────────────────────────────
# Happy-path transitions
# ──────────────────────────────────────────────────────────────

class TestValidTransitions:
    """Verify every edge in the transition map via can_transition."""

    def test_all_allowed_edges(self) -> None:
        for source, targets in TRANSITION_MAP.items():
            for target in targets:
                assert can_transition(source, target) is True, (
                    f"{source.value} → {target.value} should be allowed"
                )

    def test_main_conversation_flow(self) -> None:
        flow = [
            ConversationState.IDLE,
            ConversationState.LISTENING,
            ConversationState.TRANSCRIBING,
            ConversationState.THINKING,
            ConversationState.GENERATING_RESPONSE,
            ConversationState.GENERATING_AUDIO,
            ConversationState.SPEAKING,
            ConversationState.LISTENING,
        ]
        for i in range(len(flow) - 1):
            assert can_transition(flow[i], flow[i + 1]) is True

    def test_interrupt_flow(self) -> None:
        assert can_transition(ConversationState.SPEAKING, ConversationState.INTERRUPTED)
        assert can_transition(ConversationState.INTERRUPTED, ConversationState.LISTENING)

    def test_error_recovery(self) -> None:
        assert can_transition(ConversationState.ERROR, ConversationState.IDLE)
        assert can_transition(ConversationState.ERROR, ConversationState.CLOSED)


# ──────────────────────────────────────────────────────────────
# Invalid transitions
# ──────────────────────────────────────────────────────────────

class TestInvalidTransitions:
    @pytest.mark.parametrize("from_s,to_s", [
        (ConversationState.IDLE, ConversationState.SPEAKING),
        (ConversationState.IDLE, ConversationState.THINKING),
        (ConversationState.TRANSCRIBING, ConversationState.SPEAKING),
        (ConversationState.INTERRUPTED, ConversationState.IDLE),
        (ConversationState.ERROR, ConversationState.SPEAKING),
    ])
    def test_forbidden(self, from_s: ConversationState, to_s: ConversationState) -> None:
        assert can_transition(from_s, to_s) is False

    def test_closed_blocks_everything(self) -> None:
        for target in ConversationState:
            assert can_transition(ConversationState.CLOSED, target) is False


# ──────────────────────────────────────────────────────────────
# Validators (throwing)
# ──────────────────────────────────────────────────────────────

class TestValidateTransition:
    def test_valid_does_not_raise(self) -> None:
        validate_transition(
            ConversationState.IDLE, ConversationState.LISTENING, "s1"
        )

    def test_invalid_raises_error(self) -> None:
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(
                ConversationState.IDLE, ConversationState.SPEAKING, "s1"
            )
        assert exc_info.value.from_state == "idle"
        assert exc_info.value.to_state == "speaking"

    def test_terminal_raises_error(self) -> None:
        with pytest.raises(TerminalStateError) as exc_info:
            validate_transition(
                ConversationState.CLOSED, ConversationState.IDLE, "s1"
            )
        assert exc_info.value.session_id == "s1"
