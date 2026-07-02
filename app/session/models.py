"""
Session Model — Mutable container for a single voice-agent conversation.

Design Decision:
    Unlike Message (frozen), Session is intentionally *mutable* because its
    fields (history, state, speaking flags, latency metrics) change
    continuously during a live conversation.  The dataclass is not frozen
    so that the SessionManager can update it in place without reconstruction.

    `session_id` is generated via uuid4 for global uniqueness and is stored
    as a plain string so it can be used as a dictionary key, a Redis key, or
    a WebSocket path segment without conversion.

Future Compatibility:
    - `metadata` provides an open extension point for Pipecat-specific
      context (e.g., transport config, user profile, feature flags).
    - `latency` captures per-component timing (stt_ms, llm_ms, tts_ms)
      for the latency-monitoring processor that will be added later.
    - `to_dict()` enables JSON serialization for FastAPI responses or
      Redis HASH storage.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from .message import Message
from .state import SessionState


@dataclass(slots=True)
class Session:
    """Mutable container representing a single voice-agent session.

    Attributes:
        session_id:      Globally unique identifier (UUID v4 string).
        created_at:      UTC timestamp of session creation.
        last_activity:   UTC timestamp of the most recent interaction —
                         updated on every message add or state transition.
        history:         Ordered list of ``Message`` objects forming the
                         conversation transcript.
        current_state:   Current ``SessionState`` enum member.
        is_user_speaking: Flag indicating active user audio input.
        is_ai_speaking:   Flag indicating active TTS audio output.
        metadata:        Arbitrary key-value store for pipeline extensions
                         (transport config, feature flags, user profile, etc.).
        latency:         Per-component latency measurements in milliseconds.
                         Expected keys: ``stt_ms``, ``llm_ms``, ``tts_ms``,
                         ``total_ms``.
    """

    # ── Identity ──────────────────────────────────────────────────────
    session_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    # ── Timestamps ────────────────────────────────────────────────────
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ── Conversation ──────────────────────────────────────────────────
    history: List[Message] = field(default_factory=list)
    current_state: SessionState = SessionState.IDLE

    # ── Speaking flags ────────────────────────────────────────────────
    is_user_speaking: bool = False
    is_ai_speaking: bool = False

    # ── Extension points ──────────────────────────────────────────────
    metadata: Dict[str, str] = field(default_factory=dict)
    latency: Dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------
    @property
    def message_count(self) -> int:
        """Return the number of messages in the conversation history."""
        return len(self.history)

    @property
    def duration_seconds(self) -> float:
        """Elapsed seconds since session creation (UTC)."""
        return (
            datetime.now(timezone.utc) - self.created_at
        ).total_seconds()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def touch(self) -> None:
        """Update ``last_activity`` to the current UTC time.

        Called internally by the SessionManager on every state-changing
        operation to keep idle-timeout tracking accurate.
        """
        self.last_activity = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, object]:
        """Serialize session state to a JSON-compatible dictionary.

        Returns:
            A dictionary suitable for FastAPI JSON responses or Redis
            HASH storage.

        Example::

            >>> session = Session()
            >>> data = session.to_dict()
            >>> data["session_id"]
            'a3f1c2d4-...'
        """
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "current_state": self.current_state.value,
            "is_user_speaking": self.is_user_speaking,
            "is_ai_speaking": self.is_ai_speaking,
            "message_count": self.message_count,
            "metadata": self.metadata,
            "latency": self.latency,
            "history": [msg.to_dict() for msg in self.history],
        }

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"Session(id={self.session_id[:8]}…, "
            f"state={self.current_state.value}, "
            f"messages={self.message_count})"
        )