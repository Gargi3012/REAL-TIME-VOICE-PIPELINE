"""
Conversation Event Models — Immutable records emitted by state transitions.

Design Decision:
    Events are defined as frozen dataclasses here (models only — no bus,
    no dispatch, no handlers).  When the Event Bus is implemented in the
    next milestone, it will import these types and route them to registered
    handlers.

    Every event carries ``session_id`` and ``timestamp`` so that downstream
    consumers can correlate and order events without additional context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .transitions import ConversationState


# ──────────────────────────────────────────────────────────────────────
# Base event
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ConversationEvent:
    """Base class for all conversation events.

    Attributes:
        session_id: The session this event belongs to.
        timestamp:  UTC time the event was created.
    """

    session_id: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "event": type(self).__name__,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
        }


# ──────────────────────────────────────────────────────────────────────
# Lifecycle events
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ConversationStarted(ConversationEvent):
    """Emitted when a conversation transitions from IDLE to LISTENING."""


@dataclass(frozen=True, slots=True)
class ConversationClosed(ConversationEvent):
    """Emitted when a conversation reaches the terminal CLOSED state."""

    reason: str = "normal"


# ──────────────────────────────────────────────────────────────────────
# Pipeline stage events
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ListeningStarted(ConversationEvent):
    """Emitted when the microphone opens and audio streams to STT."""


@dataclass(frozen=True, slots=True)
class TranscriptReady(ConversationEvent):
    """Emitted when STT finishes transcribing audio to text."""


@dataclass(frozen=True, slots=True)
class ThinkingStarted(ConversationEvent):
    """Emitted when the LLM begins processing the user transcript."""


@dataclass(frozen=True, slots=True)
class ResponseGenerated(ConversationEvent):
    """Emitted when the LLM completes response generation."""


@dataclass(frozen=True, slots=True)
class AudioGenerationStarted(ConversationEvent):
    """Emitted when TTS begins synthesising audio from text."""


@dataclass(frozen=True, slots=True)
class SpeakingStarted(ConversationEvent):
    """Emitted when audio playback to the user begins."""


# ──────────────────────────────────────────────────────────────────────
# Interruption & error events
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Interrupted(ConversationEvent):
    """Emitted when the user barges in during AI speech."""


@dataclass(frozen=True, slots=True)
class ErrorOccurred(ConversationEvent):
    """Emitted when a recoverable error occurs in the pipeline.

    Attributes:
        error_message: Human-readable description of the error.
    """

    error_message: str = "Unknown error"

    def to_dict(self) -> dict[str, str]:
        d = ConversationEvent.to_dict(self)
        d["error_message"] = self.error_message
        return d


# ──────────────────────────────────────────────────────────────────────
# Transition record (not an event — used for history tracking)
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """Immutable log entry for a single state transition.

    Attributes:
        session_id:     Session this transition belongs to.
        from_state:     State before the transition.
        to_state:       State after the transition.
        timestamp:      UTC time of the transition.
        reason:         Optional human-readable reason for the transition.
    """

    session_id: str
    from_state: ConversationState
    to_state: ConversationState
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    reason: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "session_id": self.session_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
        }
