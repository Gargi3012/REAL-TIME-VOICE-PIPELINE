"""Context Manager for handling conversational window trimming."""

from typing import List
from loguru import logger

from app.session.manager import SessionManager
from app.session.message import Message


class ContextManager:
    """Sits on top of SessionManager.get_history() and trims history to last N messages."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialise the ContextManager with a SessionManager instance.

        Args:
            session_manager: The active SessionManager instance.
        """
        self.session_manager = session_manager

    def get_trimmed_history(
        self,
        session_id: str,
        max_messages: int = 10,
    ) -> List[Message]:
        """Retrieve conversation history for a session, trimmed to the last N messages.

        If a system prompt is present in the session history (typically as the first message),
        it should always be preserved at the beginning of the context (index 0) so the model
        maintains its instructions, and the sliding window of size N-1 is applied to the
        remaining messages.

        Args:
            session_id: Target session UUID.
            max_messages: The maximum number of messages to return. Must be >= 1.

        Returns:
            A list of trimmed Message objects, or an empty list if the session is not found
            or has no messages.
        """
        if max_messages < 1:
            raise ValueError("max_messages must be at least 1")

        history = self.session_manager.get_history(session_id)
        if history is None:
            logger.bind(session_id=session_id).warning(
                "Cannot retrieve history — session not found"
            )
            return []

        if not history:
            return []

        total_count = len(history)
        if total_count <= max_messages:
            return history

        # Check if the first message has a system role.
        # If it does, we preserve it and apply sliding window to the rest.
        if history[0].role == "system":
            system_message = history[0]
            non_system_history = history[1:]

            # We need to take max_messages - 1 from the rest.
            sliding_window_size = max(0, max_messages - 1)
            trimmed_rest = (
                non_system_history[-sliding_window_size:]
                if sliding_window_size > 0
                else []
            )

            trimmed_history = [system_message] + trimmed_rest
            logger.bind(session_id=session_id).debug(
                "Trimmed session history with preserved system prompt | "
                "original={original} | trimmed={trimmed}",
                original=total_count,
                trimmed=len(trimmed_history),
            )
            return trimmed_history

        # If there is no system message at the start, simply slice the last N.
        trimmed_history = history[-max_messages:]
        logger.bind(session_id=session_id).debug(
            "Trimmed session history (no system prompt at start) | "
            "original={original} | trimmed={trimmed}",
            original=total_count,
            trimmed=len(trimmed_history),
        )
        return trimmed_history
