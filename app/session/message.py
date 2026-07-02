"""
Message Model — Immutable record of a single conversational turn.

Design Decision:
    The Message dataclass is kept frozen (immutable) to guarantee referential
    integrity once a message enters the conversation history.  Immutability
    also makes Messages safe to share across async tasks without locks.

    `Role` is expressed as a Literal type rather than an Enum so that it
    serializes directly to the string values expected by LLM APIs (OpenAI,
    Gemini, Groq) without an extra .value accessor.

Future Compatibility:
    - Can be serialized to dict/JSON for Redis persistence or WebSocket push.
    - Frozen dataclass is inherently thread-safe for asyncio concurrency.
    - `to_dict()` output aligns with the chat-completion message format used
      by most LLM providers, enabling zero-transform forwarding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

# ---------------------------------------------------------------------------
# Type alias for allowed message roles.
# Using Literal (not Enum) keeps serialization trivial and aligns with the
# message schema expected by OpenAI-compatible LLM APIs.
# ---------------------------------------------------------------------------
Role = Literal["system", "user", "assistant"]

# Expose the valid role values for runtime validation outside type-checkers.
VALID_ROLES: frozenset[str] = frozenset({"system", "user", "assistant"})


@dataclass(frozen=True, slots=True)
class Message:
    """Immutable record of a single conversational message.

    Attributes:
        role:      The speaker — one of ``"system"``, ``"user"``, or
                   ``"assistant"``.
        content:   The textual content of the message.
        timestamp: UTC datetime when the message was created.  Defaults to
                   the current time via a ``default_factory`` to avoid the
                   mutable-default-argument pitfall.
    """

    role: Role
    content: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        """Validate fields immediately after construction.

        Raises:
            ValueError: If ``role`` is not one of the allowed values or
                        ``content`` is empty / whitespace-only.
        """
        if self.role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{self.role}'. "
                f"Allowed roles: {', '.join(sorted(VALID_ROLES))}"
            )
        if not self.content or not self.content.strip():
            raise ValueError("Message content must not be empty.")

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, str]:
        """Serialize to a dict compatible with LLM chat-completion APIs.

        Returns:
            A dictionary with ``role``, ``content``, and ``timestamp`` keys.

        Example::

            >>> msg = Message(role="user", content="Hello")
            >>> msg.to_dict()
            {'role': 'user', 'content': 'Hello', 'timestamp': '2026-...'}
        """
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        """Concise developer-friendly representation."""
        preview = (
            self.content[:40] + "…" if len(self.content) > 40 else self.content
        )
        return (
            f"Message(role={self.role!r}, content={preview!r}, "
            f"timestamp={self.timestamp.isoformat()})"
        )