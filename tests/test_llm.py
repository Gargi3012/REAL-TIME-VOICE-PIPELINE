"""Tests for app.llm module — prompts, client structure, and context manager."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.session import Message, SessionManager
from app.llm.prompts import VOICE_SYSTEM_PROMPT
from app.llm.client import GroqLLMClient
from app.llm.context_manager import ContextManager


class TestVoicePrompts:
    def test_voice_prompt_sanity(self) -> None:
        """Verify the voice system prompt is defined, non-empty, and concise."""
        assert isinstance(VOICE_SYSTEM_PROMPT, str)
        assert len(VOICE_SYSTEM_PROMPT) > 0
        # Ensure it has no markdown markers
        assert "#" not in VOICE_SYSTEM_PROMPT
        assert "*" not in VOICE_SYSTEM_PROMPT
        assert "-" not in VOICE_SYSTEM_PROMPT
        assert "1." not in VOICE_SYSTEM_PROMPT


class TestContextManager:
    def test_get_trimmed_history_empty_session(self, manager: SessionManager) -> None:
        """Verify trimming empty session returns empty list."""
        ctx_mgr = ContextManager(manager)
        assert ctx_mgr.get_trimmed_history("non-existent-session-id") == []

    def test_get_trimmed_history_shorter_than_max(self, manager: SessionManager) -> None:
        """Verify that if history is shorter than max, entire history is returned."""
        ctx_mgr = ContextManager(manager)
        s = manager.create_session()
        manager.add_message(s.session_id, "user", "hi")
        manager.add_message(s.session_id, "assistant", "hello")
        
        trimmed = ctx_mgr.get_trimmed_history(s.session_id, max_messages=5)
        assert len(trimmed) == 2
        assert trimmed[0].content == "hi"
        assert trimmed[1].content == "hello"

    def test_get_trimmed_history_no_system_prompt(self, manager: SessionManager) -> None:
        """Verify sliding window trims to last N when no system prompt is present."""
        ctx_mgr = ContextManager(manager)
        s = manager.create_session()
        for i in range(5):
            manager.add_message(s.session_id, "user", f"message {i}")
            
        trimmed = ctx_mgr.get_trimmed_history(s.session_id, max_messages=3)
        assert len(trimmed) == 3
        assert trimmed[0].content == "message 2"
        assert trimmed[1].content == "message 3"
        assert trimmed[2].content == "message 4"

    def test_get_trimmed_history_preserves_system_prompt(self, manager: SessionManager) -> None:
        """Verify system prompt at index 0 is preserved, and rest is trimmed to max-1."""
        ctx_mgr = ContextManager(manager)
        s = manager.create_session()
        manager.add_message(s.session_id, "system", VOICE_SYSTEM_PROMPT)
        for i in range(5):
            manager.add_message(s.session_id, "user", f"message {i}")
            
        # max_messages=4 should return 1 system prompt + 3 last user messages (message 2, 3, 4)
        trimmed = ctx_mgr.get_trimmed_history(s.session_id, max_messages=4)
        assert len(trimmed) == 4
        assert trimmed[0].role == "system"
        assert trimmed[0].content == VOICE_SYSTEM_PROMPT
        assert trimmed[1].content == "message 2"
        assert trimmed[2].content == "message 3"
        assert trimmed[3].content == "message 4"

    def test_get_trimmed_history_invalid_max_messages(self, manager: SessionManager) -> None:
        """Verify raising error if max_messages < 1."""
        ctx_mgr = ContextManager(manager)
        s = manager.create_session()
        with pytest.raises(ValueError, match="max_messages must be at least 1"):
            ctx_mgr.get_trimmed_history(s.session_id, max_messages=0)


class TestGroqLLMClient:
    def test_init_raises_without_api_key(self) -> None:
        """Verify initialization raises ValueError if no api_key is present in env or arguments."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GROQ_API_KEY is not set"):
                GroqLLMClient()

    def test_init_with_argument_api_key(self) -> None:
        """Verify key can be passed via constructor parameter."""
        with patch.dict(os.environ, {}, clear=True):
            client = GroqLLMClient(api_key="gsk_testkey")
            assert client.api_key == "gsk_testkey"

    def test_init_with_env_api_key(self) -> None:
        """Verify key can be read from environment variable."""
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_envkey"}):
            client = GroqLLMClient()
            assert client.api_key == "gsk_envkey"

    @pytest.mark.asyncio
    async def test_stream_response(self) -> None:
        """Verify stream_response converts messages correctly and yields chunks."""
        client = GroqLLMClient(api_key="gsk_dummy")
        
        # Mocking the AsyncGroq client chat.completions.create response
        mock_response = MagicMock()
        
        # Async iterator helper for mock response
        class AsyncIterator:
            def __init__(self, items):
                self.items = items
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self.items:
                    raise StopAsyncIteration
                return self.items.pop(0)
                
        mock_chunk_1 = MagicMock()
        mock_chunk_1.choices = [MagicMock()]
        mock_chunk_1.choices[0].delta.content = "Hello"
        
        mock_chunk_2 = MagicMock()
        mock_chunk_2.choices = [MagicMock()]
        mock_chunk_2.choices[0].delta.content = " world"
        
        client.client.chat.completions.create = AsyncMock(
            return_value=AsyncIterator([mock_chunk_1, mock_chunk_2])
        )
        
        messages = [
            Message(role="system", content="prompt"),
            Message(role="user", content="hello"),
        ]
        
        chunks = []
        async for chunk in client.stream_response(messages):
            chunks.append(chunk)
            
        assert chunks == ["Hello", " world"]
        
        # Verify it was called with correct parameters
        client.client.chat.completions.create.assert_called_once_with(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "prompt"},
                {"role": "user", "content": "hello"},
            ],
            stream=True
        )
