"""
Conversation State Transitions — The single source of truth for the FSM.

Design Decision:
    The transition map is a module-level constant (frozenset values inside a
    dict) so it is immutable at runtime.  Every transition in the system is
    validated against this map — no ad-hoc checks scattered across code.

    ConversationState is a *separate* enum from session.SessionState because
    the conversation FSM is more granular (10 states vs 6).  The session
    layer tracks coarse lifecycle; the conversation layer tracks the
    detailed pipeline flow.  A mapping function is provided for integration.

Transition Rules:
    IDLE               → LISTENING, CLOSED
    LISTENING          → TRANSCRIBING, INTERRUPTED, ERROR, CLOSED
    TRANSCRIBING       → THINKING, ERROR, CLOSED
    THINKING           → GENERATING_RESPONSE, ERROR, CLOSED
    GENERATING_RESPONSE→ GENERATING_AUDIO, ERROR, CLOSED
    GENERATING_AUDIO   → SPEAKING, ERROR, CLOSED
    SPEAKING           → LISTENING, INTERRUPTED, IDLE, ERROR, CLOSED
    INTERRUPTED        → LISTENING, CLOSED
    ERROR              → IDLE, CLOSED
    CLOSED             → (terminal — no outgoing transitions)
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet


class ConversationState(Enum):
    """Fine-grained states for the voice conversation pipeline.

    Compared to ``SessionState`` (6 states), this enum models each
    processing stage individually so that latency monitoring, UI
    indicators, and pipeline processors can react precisely.

    Attributes:
        IDLE:                 No active processing; awaiting user input.
        LISTENING:            Microphone open, audio streaming to STT.
        TRANSCRIBING:         STT is converting buffered audio to text.
        THINKING:             LLM is processing the transcript.
        GENERATING_RESPONSE:  LLM is streaming response tokens.
        GENERATING_AUDIO:     TTS is synthesising audio from text.
        SPEAKING:             Audio is being played back to the user.
        INTERRUPTED:          User barged in during AI speech.
        ERROR:                A recoverable error occurred in the pipeline.
        CLOSED:               Terminal state — conversation has ended.
    """

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    GENERATING_RESPONSE = "generating_response"
    GENERATING_AUDIO = "generating_audio"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"
    CLOSED = "closed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def is_terminal(self) -> bool:
        """Return True if this is the terminal CLOSED state."""
        return self is ConversationState.CLOSED

    def is_processing(self) -> bool:
        """Return True if the pipeline is actively processing."""
        return self in _PROCESSING_STATES

    def is_error(self) -> bool:
        """Return True if the conversation is in an error state."""
        return self is ConversationState.ERROR


# States considered "actively processing" (for is_processing helper)
_PROCESSING_STATES: FrozenSet[ConversationState] = frozenset({
    ConversationState.LISTENING,
    ConversationState.TRANSCRIBING,
    ConversationState.THINKING,
    ConversationState.GENERATING_RESPONSE,
    ConversationState.GENERATING_AUDIO,
    ConversationState.SPEAKING,
})

# ──────────────────────────────────────────────────────────────────────
# TRANSITION MAP — the single source of truth
# ──────────────────────────────────────────────────────────────────────
# Key: source state → Value: frozenset of allowed target states
TRANSITION_MAP: Dict[ConversationState, FrozenSet[ConversationState]] = {
    ConversationState.IDLE: frozenset({
        ConversationState.LISTENING,
        ConversationState.CLOSED,
    }),
    ConversationState.LISTENING: frozenset({
        ConversationState.TRANSCRIBING,
        ConversationState.THINKING,  # Allowed for AI-initiated greetings without transcript
        ConversationState.GENERATING_RESPONSE, # LLM still streaming chunks
        ConversationState.GENERATING_AUDIO,    # TTS resuming after a pause
        ConversationState.SPEAKING,            # Allowed for initial AI greetings & resumption after interruption
        ConversationState.INTERRUPTED,
        ConversationState.ERROR,
        ConversationState.CLOSED,
    }),
    ConversationState.TRANSCRIBING: frozenset({
        ConversationState.THINKING,
        ConversationState.INTERRUPTED,
        ConversationState.ERROR,
        ConversationState.CLOSED,
    }),
    ConversationState.THINKING: frozenset({
        ConversationState.GENERATING_RESPONSE,
        ConversationState.GENERATING_AUDIO, # Allowed if intermediate tokens aren't tracked
        ConversationState.TRANSCRIBING,     # User barged in while thinking
        ConversationState.INTERRUPTED,
        ConversationState.ERROR,
        ConversationState.CLOSED,
    }),
    ConversationState.GENERATING_RESPONSE: frozenset({
        ConversationState.GENERATING_AUDIO,
        ConversationState.SPEAKING,         # TTS starts before LLM finishes
        ConversationState.TRANSCRIBING,     # User barged in
        ConversationState.INTERRUPTED,
        ConversationState.ERROR,
        ConversationState.CLOSED,
    }),
    ConversationState.GENERATING_AUDIO: frozenset({
        ConversationState.SPEAKING,
        ConversationState.LISTENING,        # LLM finished or stream dropped
        ConversationState.TRANSCRIBING,     # User barged in
        ConversationState.INTERRUPTED,
        ConversationState.ERROR,
        ConversationState.CLOSED,
    }),
    ConversationState.SPEAKING: frozenset({
        ConversationState.LISTENING,
        ConversationState.TRANSCRIBING,     # User barged in
        ConversationState.INTERRUPTED,
        ConversationState.IDLE,
        ConversationState.ERROR,
        ConversationState.CLOSED,
        ConversationState.GENERATING_AUDIO, # LLM response finishes after TTS started
    }),
    ConversationState.INTERRUPTED: frozenset({
        ConversationState.LISTENING,
        ConversationState.CLOSED,
    }),
    ConversationState.ERROR: frozenset({
        ConversationState.IDLE,
        ConversationState.CLOSED,
    }),
    ConversationState.CLOSED: frozenset(),  # terminal — no outgoing edges
}


def get_allowed_transitions(
    state: ConversationState,
) -> FrozenSet[ConversationState]:
    """Return the set of states reachable from ``state``.

    Args:
        state: The current conversation state.

    Returns:
        A frozenset of ``ConversationState`` members that ``state`` may
        transition to.
    """
    return TRANSITION_MAP.get(state, frozenset())
