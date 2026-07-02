"""
Session Manager — Centralised CRUD + conversation operations for voice sessions.

Design Decisions:

1.  **In-memory dict store**:  The current implementation uses a plain
    ``dict[str, Session]`` for zero-dependency local development.  The
    manager is structured behind a clean public API so that the backing
    store can be swapped to Redis, PostgreSQL, or any async store by
    implementing the same interface (see ``_sessions`` access pattern).

2.  **Thread-safety via threading.Lock**:  A reentrant lock guards every
    mutation.  This is sufficient for multi-threaded ASGI servers
    (Uvicorn with workers) and can later be replaced with
    ``asyncio.Lock`` when the manager is made fully async.

3.  **Optional[Session] returns**:  ``get_session`` returns ``None``
    rather than raising on missing keys, following the "ask forgiveness"
    pattern.  The caller decides whether a missing session is an error.

4.  **Loguru logging**:  Structured log lines use Loguru's ``bind()``
    context for session_id so that log aggregators (Datadog, Loki) can
    filter by session without parsing free-text messages.

Future Compatibility:
    - Replace ``dict`` with an async Redis client for distributed state.
    - Add ``async`` variants of every public method for asyncio pipelines.
    - Expose via FastAPI dependency injection (``Depends(get_session_manager)``).
    - Add TTL-based auto-cleanup for idle sessions.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from loguru import logger

from .message import Message, Role
from .models import Session
from .state import SessionState


class SessionManager:
    """Centralised manager for voice-agent session lifecycle and conversation state.

    Responsibilities:
        - Create, retrieve, list, and delete sessions.
        - Append messages to a session's conversation history.
        - Track activity timestamps for idle-timeout enforcement.

    Thread Safety:
        All public methods acquire ``_lock`` before mutating ``_sessions``.
        Safe for use with multi-threaded ASGI servers (e.g., Uvicorn workers).

    Example::

        manager = SessionManager()
        session = manager.create_session()
        manager.add_message(session.session_id, role="user", content="Hi!")
        history = manager.get_history(session.session_id)
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        """Initialise the session manager with an empty in-memory store.

        The backing ``_sessions`` dict is guarded by a reentrant lock so
        that concurrent request handlers cannot corrupt state.
        """
        self._sessions: Dict[str, Session] = {}
        self._lock: threading.Lock = threading.Lock()

        logger.info("SessionManager initialised (in-memory store)")

    # ==================================================================
    #  SESSION LIFECYCLE
    # ==================================================================

    def create_session(self, metadata: Optional[Dict[str, str]] = None) -> Session:
        """Create a new session and register it in the store.

        Args:
            metadata: Optional key-value pairs to attach to the session
                      (e.g., user_id, transport type, feature flags).

        Returns:
            The newly created ``Session`` instance.
        """
        session = Session(metadata=metadata or {})

        with self._lock:
            self._sessions[session.session_id] = session

        logger.bind(session_id=session.session_id).info(
            "Session created | state={state}",
            state=session.current_state.value,
        )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by its ID.

        Args:
            session_id: The UUID string of the target session.

        Returns:
            The ``Session`` if found, otherwise ``None``.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Attempted access to non-existent session"
            )

        return session

    def delete_session(self, session_id: str) -> bool:
        """Remove a session from the store.

        The session's state is set to ``CLOSED`` before removal so that
        any references still held elsewhere can detect termination.

        Args:
            session_id: The UUID string of the target session.

        Returns:
            ``True`` if the session was found and deleted, ``False`` otherwise.
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Attempted to delete non-existent session"
            )
            return False

        # Mark as closed so stale references see the terminal state.
        session.current_state = SessionState.CLOSED
        session.touch()

        logger.bind(session_id=session_id).info(
            "Session deleted | messages={count} | duration={dur:.1f}s",
            count=session.message_count,
            dur=session.duration_seconds,
        )
        return True

    def list_sessions(self) -> List[Session]:
        """Return a snapshot list of all active sessions.

        Returns:
            A shallow copy of the sessions list to prevent external
            mutation of the internal store.
        """
        with self._lock:
            return list(self._sessions.values())

    def session_exists(self, session_id: str) -> bool:
        """Check whether a session is registered.

        Args:
            session_id: The UUID string to look up.

        Returns:
            ``True`` if the session exists in the store.
        """
        with self._lock:
            return session_id in self._sessions

    def total_sessions(self) -> int:
        """Return the number of currently active sessions.

        Returns:
            Integer count of sessions in the store.
        """
        with self._lock:
            return len(self._sessions)

    # ==================================================================
    #  CONVERSATION MANAGEMENT
    # ==================================================================

    def add_message(
        self,
        session_id: str,
        role: Role,
        content: str,
    ) -> Optional[Message]:
        """Append a message to a session's conversation history.

        This is the primary ingestion point for all conversational turns —
        STT transcripts (``"user"``), LLM completions (``"assistant"``),
        and system prompts (``"system"``).

        Args:
            session_id: Target session UUID.
            role:       One of ``"system"``, ``"user"``, or ``"assistant"``.
            content:    The textual content of the message.

        Returns:
            The created ``Message`` on success, or ``None`` if the
            session was not found.

        Raises:
            ValueError: If ``role`` or ``content`` fails Message validation.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Cannot add message — session not found"
            )
            return None

        # Message.__post_init__ validates role + content; let it raise.
        message = Message(role=role, content=content)

        with self._lock:
            session.history.append(message)
            session.touch()

        logger.bind(session_id=session_id).debug(
            "Message added | role={role} | length={length}",
            role=role,
            length=len(content),
        )
        return message

    def get_history(self, session_id: str) -> Optional[List[Message]]:
        """Retrieve the full conversation history for a session.

        Args:
            session_id: Target session UUID.

        Returns:
            A **copy** of the message list (so callers cannot mutate the
            internal history), or ``None`` if the session is not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Cannot retrieve history — session not found"
            )
            return None

        # Return a shallow copy to prevent external list mutations.
        return list(session.history)

    def clear_history(self, session_id: str) -> bool:
        """Remove all messages from a session's conversation history.

        Args:
            session_id: Target session UUID.

        Returns:
            ``True`` if the history was cleared, ``False`` if the session
            was not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Cannot clear history — session not found"
            )
            return False

        cleared_count = len(session.history)

        with self._lock:
            session.history.clear()
            session.touch()

        logger.bind(session_id=session_id).info(
            "History cleared | removed={count} messages",
            count=cleared_count,
        )
        return True

    # ==================================================================
    #  ACTIVITY TRACKING
    # ==================================================================

    def update_last_activity(self, session_id: str) -> bool:
        """Manually refresh the ``last_activity`` timestamp of a session.

        Useful for keep-alive pings or non-message interactions (e.g.,
        WebSocket heartbeats) that should prevent idle-timeout cleanup.

        Args:
            session_id: Target session UUID.

        Returns:
            ``True`` if the session was found and updated, ``False`` otherwise.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Cannot update activity — session not found"
            )
            return False

        session.touch()

        logger.bind(session_id=session_id).debug(
            "Last activity updated | ts={ts}",
            ts=session.last_activity.isoformat(),
        )
        return True

    # ==================================================================
    #  STATE TRANSITIONS  (prepared for future Pipecat integration)
    # ==================================================================

    def set_state(self, session_id: str, new_state: SessionState) -> bool:
        """Transition a session to a new state.

        Args:
            session_id: Target session UUID.
            new_state:  The ``SessionState`` to transition to.

        Returns:
            ``True`` if the transition succeeded, ``False`` if the session
            was not found or is already CLOSED.
        """
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            logger.bind(session_id=session_id).warning(
                "Cannot set state — session not found"
            )
            return False

        if session.current_state.is_terminal():
            logger.bind(session_id=session_id).warning(
                "Cannot transition from terminal state CLOSED"
            )
            return False

        old_state = session.current_state

        with self._lock:
            session.current_state = new_state
            session.touch()

        logger.bind(session_id=session_id).info(
            "State transition | {old} → {new}",
            old=old_state.value,
            new=new_state.value,
        )
        return True

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return f"SessionManager(active_sessions={self.total_sessions()})"

    def __len__(self) -> int:
        return self.total_sessions()
