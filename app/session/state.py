"""
Session State Enum — Defines the finite set of states a voice session can occupy.

Design Decision:
    Using an Enum enforces compile-time safety over raw strings. Every state
    transition in the pipeline will reference these enum members, eliminating
    typo-driven bugs and enabling exhaustive pattern matching in future
    Pipecat processors.

Future Compatibility:
    - Pipecat pipeline processors will dispatch behavior based on these states.
    - FastAPI WebSocket handlers can serialize state via .value for JSON transport.
    - Redis pub/sub channels can use state values as event discriminators.
"""

from enum import Enum


class SessionState(Enum):
    """Finite state machine representation for a voice session lifecycle.

    States follow a natural conversational flow:
        IDLE → LISTENING → THINKING → SPEAKING → IDLE
                                        ↓
                                   INTERRUPTED → IDLE
        Any state → CLOSED (terminal)

    Attributes:
        IDLE:        Session exists but no active audio processing.
        LISTENING:   STT is actively transcribing user speech.
        THINKING:    LLM is generating a response.
        SPEAKING:    TTS is synthesizing and streaming audio output.
        INTERRUPTED: User barged in during AI speech; pipeline is resetting.
        CLOSED:      Terminal state — session resources have been released.
    """

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"

    def is_active(self) -> bool:
        """Check whether the session is in a non-terminal, non-idle state.

        Returns:
            True if the session is actively processing audio or generating
            a response.
        """
        return self in (
            SessionState.LISTENING,
            SessionState.THINKING,
            SessionState.SPEAKING,
        )

    def is_terminal(self) -> bool:
        """Check whether the session has reached a terminal state.

        Returns:
            True if the session is closed and cannot transition further.
        """
        return self == SessionState.CLOSED
