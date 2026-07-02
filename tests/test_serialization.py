"""
Serialization tests — JSON roundtrip for Message and Session.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.session import SessionManager, Session, Message, SessionState


class TestMessageSerialization:
    def test_json_roundtrip(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        msg = Message(role="user", content="hello world", timestamp=ts)
        d = msg.to_dict()
        s = json.dumps(d)
        rt = json.loads(s)
        assert rt["role"] == "user"
        assert rt["content"] == "hello world"
        assert rt["timestamp"] == "2025-06-15T12:00:00+00:00"

    def test_unicode_serialization(self) -> None:
        msg = Message(role="user", content="日本語テスト 🎌")
        s = json.dumps(msg.to_dict(), ensure_ascii=False)
        rt = json.loads(s)
        assert rt["content"] == "日本語テスト 🎌"

    def test_all_roles_serialize(self) -> None:
        for role in ("system", "user", "assistant"):
            d = Message(role=role, content="test").to_dict()  # type: ignore[arg-type]
            assert d["role"] == role


class TestSessionSerialization:
    def test_empty_session_json(self) -> None:
        s = Session()
        serialized = json.dumps(s.to_dict())
        rt = json.loads(serialized)
        assert rt["current_state"] == "idle"
        assert rt["history"] == []
        assert rt["message_count"] == 0

    def test_session_with_history(self) -> None:
        s = Session()
        s.history.append(Message(role="system", content="You are a bot."))
        s.history.append(Message(role="user", content="Hello"))
        s.history.append(Message(role="assistant", content="Hi!"))
        rt = json.loads(json.dumps(s.to_dict()))
        assert len(rt["history"]) == 3
        assert rt["history"][0]["role"] == "system"
        assert rt["message_count"] == 3

    def test_session_with_latency(self) -> None:
        s = Session()
        s.latency = {"stt_ms": 42.5, "llm_ms": 150.0, "tts_ms": 80.0}
        rt = json.loads(json.dumps(s.to_dict()))
        assert rt["latency"]["stt_ms"] == 42.5

    def test_session_with_metadata(self) -> None:
        s = Session(metadata={"user_id": "abc", "lang": "en"})
        rt = json.loads(json.dumps(s.to_dict()))
        assert rt["metadata"]["user_id"] == "abc"

    def test_timestamps_parseable(self) -> None:
        d = Session().to_dict()
        datetime.fromisoformat(d["created_at"])
        datetime.fromisoformat(d["last_activity"])
