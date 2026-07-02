"""
Session Package — Public API surface for the session management layer.

Import Convention:
    Downstream modules (API routes, pipeline processors) import from the
    package root so they are decoupled from internal file layout::

        from app.session import SessionManager, Session, Message, SessionState

    This keeps the internal module structure free to evolve without
    breaking external imports.
"""

from .manager import SessionManager
from .message import Message, Role, VALID_ROLES
from .models import Session
from .state import SessionState

__all__: list[str] = [
    "SessionManager",
    "Session",
    "Message",
    "SessionState",
    "Role",
    "VALID_ROLES",
]
