"""
Tests for app.session.models — Session dataclass.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import pytest

from app.session.models import Session
from app.session.message import Message
from app.session.state import SessionState


class TestSessionDefaults:
    def test_session_id_is_uuid4(self) -> None:
        uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
        assert uuid_re.match(Session().session_id)

    def test_unique_ids(self) -> None:
        assert len({Session().session_id for _ in range(100)}) == 100

    def test_default_state_idle(self) -> None:
        assert Session().current_state == SessionState.IDLE

    def test_default_flags(self) -> None:
        s = Session()
        assert s.is_user_speaking is False and s.is_ai_speaking is False

    def test_defaults_empty(self) -> None:
        s = Session()
        assert s.history == [] and s.metadata == {} and s.latency == {}

    def test_timezone_aware(self) -> None:
        s = Session()
        assert s.created_at.tzinfo is not None and s.last_activity.tzinfo is not None

    def test_no_shared_defaults(self) -> None:
        s1, s2 = Session(), Session()
        assert s1.history is not s2.history
        assert s1.metadata is not s2.metadata


class TestSessionProperties:
    def test_message_count(self) -> None:
        s = Session()
        assert s.message_count == 0
        s.history.append(Message(role="user", content="hi"))
        assert s.message_count == 1

    def test_duration(self) -> None:
        s = Session()
        time.sleep(0.05)
        assert s.duration_seconds >= 0.04


class TestSessionTouch:
    def test_touch_updates(self) -> None:
        s = Session()
        old = s.last_activity
        time.sleep(0.01)
        s.touch()
        assert s.last_activity > old

    def test_touch_preserves_created_at(self) -> None:
        s = Session()
        orig = s.created_at
        s.touch()
        assert s.created_at == orig


class TestSessionToDict:
    def test_keys(self) -> None:
        expected = {"session_id", "created_at", "last_activity", "current_state",
                    "is_user_speaking", "is_ai_speaking", "message_count",
                    "metadata", "latency", "history"}
        assert set(Session().to_dict().keys()) == expected

    def test_json_safe(self) -> None:
        s = Session()
        s.history.append(Message(role="user", content="test"))
        rt = json.loads(json.dumps(s.to_dict()))
        assert rt["session_id"] == s.session_id
        assert len(rt["history"]) == 1

    def test_state_serialized_as_string(self) -> None:
        assert Session().to_dict()["current_state"] == "idle"


class TestSessionRepr:
    def test_repr(self) -> None:
        s = Session()
        r = repr(s)
        assert s.session_id[:8] in r and "idle" in r
