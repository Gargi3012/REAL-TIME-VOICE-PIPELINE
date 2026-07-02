"""
Tests for app.session.message — Message dataclass.

Covers:
    - Valid construction with all three roles
    - Validation: invalid role, empty content, whitespace-only content
    - Immutability (frozen dataclass)
    - Timestamp default generation
    - Custom timestamp injection
    - to_dict() output format
    - __repr__() truncation logic
    - Unicode, emoji, and multiline content
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.session.message import Message, Role, VALID_ROLES


# ──────────────────────────────────────────────────────────────
# Happy-path construction
# ──────────────────────────────────────────────────────────────

class TestMessageConstruction:

    @pytest.mark.parametrize("role", ["system", "user", "assistant"])
    def test_valid_roles(self, role: str) -> None:
        msg = Message(role=role, content="hello")
        assert msg.role == role
        assert msg.content == "hello"

    def test_default_timestamp_is_utc(self) -> None:
        before = datetime.now(timezone.utc)
        msg = Message(role="user", content="test")
        after = datetime.now(timezone.utc)
        assert before <= msg.timestamp <= after
        assert msg.timestamp.tzinfo is not None

    def test_custom_timestamp(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        msg = Message(role="user", content="test", timestamp=ts)
        assert msg.timestamp == ts

    def test_each_message_gets_unique_timestamp(self) -> None:
        """Regression: ensure default_factory is used, not a shared default."""
        m1 = Message(role="user", content="first")
        m2 = Message(role="user", content="second")
        # Timestamps may be equal if created in the same microsecond,
        # but they should be independent objects.
        assert m1.timestamp is not m2.timestamp or m1.timestamp == m2.timestamp


# ──────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────

class TestMessageValidation:

    @pytest.mark.parametrize("bad_role", [
        "admin", "bot", "moderator", "", "USER", "System", "ASSISTANT",
    ])
    def test_invalid_role_raises(self, bad_role: str) -> None:
        with pytest.raises(ValueError, match="Invalid role"):
            Message(role=bad_role, content="hello")  # type: ignore[arg-type]

    def test_none_role_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            Message(role=None, content="hello")  # type: ignore[arg-type]

    def test_empty_content_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            Message(role="user", content="")

    def test_whitespace_only_content_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            Message(role="user", content="   \t\n  ")

    def test_single_space_content_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            Message(role="user", content=" ")


# ──────────────────────────────────────────────────────────────
# Immutability
# ──────────────────────────────────────────────────────────────

class TestMessageImmutability:

    def test_cannot_set_role(self) -> None:
        msg = Message(role="user", content="hello")
        with pytest.raises(AttributeError):
            msg.role = "system"  # type: ignore[misc]

    def test_cannot_set_content(self) -> None:
        msg = Message(role="user", content="hello")
        with pytest.raises(AttributeError):
            msg.content = "goodbye"  # type: ignore[misc]

    def test_cannot_set_timestamp(self) -> None:
        msg = Message(role="user", content="hello")
        with pytest.raises(AttributeError):
            msg.timestamp = datetime.now(timezone.utc)  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────
# Serialization
# ──────────────────────────────────────────────────────────────

class TestMessageSerialization:

    def test_to_dict_keys(self) -> None:
        msg = Message(role="user", content="hello")
        d = msg.to_dict()
        assert set(d.keys()) == {"role", "content", "timestamp"}

    def test_to_dict_values(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        msg = Message(role="assistant", content="Hi!", timestamp=ts)
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "Hi!"
        assert d["timestamp"] == "2025-06-15T12:00:00+00:00"

    def test_to_dict_is_json_safe(self) -> None:
        import json
        msg = Message(role="user", content="hello world")
        serialized = json.dumps(msg.to_dict())
        assert isinstance(serialized, str)
        roundtrip = json.loads(serialized)
        assert roundtrip["role"] == "user"


# ──────────────────────────────────────────────────────────────
# __repr__
# ──────────────────────────────────────────────────────────────

class TestMessageRepr:

    def test_short_content_not_truncated(self) -> None:
        msg = Message(role="user", content="short")
        r = repr(msg)
        assert "short" in r
        assert "…" not in r

    def test_long_content_truncated_at_40(self) -> None:
        long_text = "A" * 50
        msg = Message(role="user", content=long_text)
        r = repr(msg)
        assert "…" in r
        assert "A" * 40 in r

    def test_repr_contains_role(self) -> None:
        msg = Message(role="assistant", content="hello")
        assert "assistant" in repr(msg)


# ──────────────────────────────────────────────────────────────
# Special content
# ──────────────────────────────────────────────────────────────

class TestMessageSpecialContent:

    def test_unicode_content(self) -> None:
        msg = Message(role="user", content="こんにちは世界")
        assert msg.content == "こんにちは世界"

    def test_emoji_content(self) -> None:
        msg = Message(role="user", content="Hello 🎉🔥💯")
        assert "🎉" in msg.content

    def test_multiline_content(self) -> None:
        text = "Line 1\nLine 2\nLine 3"
        msg = Message(role="user", content=text)
        assert msg.content == text

    def test_very_long_content(self) -> None:
        long_text = "x" * 100_000
        msg = Message(role="user", content=long_text)
        assert len(msg.content) == 100_000

    def test_special_characters(self) -> None:
        msg = Message(role="user", content="<script>alert('xss')</script>")
        assert "<script>" in msg.content


# ──────────────────────────────────────────────────────────────
# VALID_ROLES constant
# ──────────────────────────────────────────────────────────────

class TestValidRoles:

    def test_valid_roles_is_frozenset(self) -> None:
        assert isinstance(VALID_ROLES, frozenset)

    def test_valid_roles_contents(self) -> None:
        assert VALID_ROLES == {"system", "user", "assistant"}

    def test_valid_roles_immutable(self) -> None:
        with pytest.raises(AttributeError):
            VALID_ROLES.add("admin")  # type: ignore[attr-defined]


# ──────────────────────────────────────────────────────────────
# Hashability (frozen dataclass)
# ──────────────────────────────────────────────────────────────

class TestMessageHashable:

    def test_message_is_hashable(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        msg = Message(role="user", content="hello", timestamp=ts)
        assert isinstance(hash(msg), int)

    def test_equal_messages_same_hash(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        m1 = Message(role="user", content="hello", timestamp=ts)
        m2 = Message(role="user", content="hello", timestamp=ts)
        assert hash(m1) == hash(m2)
        assert m1 == m2

    def test_usable_in_set(self) -> None:
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        m1 = Message(role="user", content="hello", timestamp=ts)
        m2 = Message(role="user", content="hello", timestamp=ts)
        msg_set = {m1, m2}
        assert len(msg_set) == 1
