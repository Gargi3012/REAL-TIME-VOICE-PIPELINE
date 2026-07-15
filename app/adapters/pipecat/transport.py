"""
Transport abstractions for Pipecat.
"""

import abc
import os
import sys
from typing import Any
from fastapi import WebSocket
import importlib.util
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.audio.vad.vad_analyzer import VADParams

def _import_pillar2_module(module_name: str, file_name: str):
    """Helper to load Pillar 2 modules without sys.path conflicts."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Pillar_2", file_name))
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PipecatTransportAdapter(abc.ABC):
    """Abstract interface for wrapping a Pipecat Transport."""

    @abc.abstractmethod
    def get_pipecat_transport(self) -> Any:
        """Return the underlying Pipecat transport instance."""
        pass


def _build_vad_analyzer():
    # Calling VAD analyzer from Pillar_2 as requested by user
    pillar2_pipeline = _import_pillar2_module("pillar2_pipeline", "pipeline.py")
    return pillar2_pipeline.build_vad_analyzer()


class TwilioTransportAdapter(PipecatTransportAdapter):
    """Implementation for Twilio WebSockets."""

    def __init__(self, websocket: WebSocket, stream_sid: str):
        # Call Pillar_2 factory
        pillar2_twilio = _import_pillar2_module("pillar2_twilio", "twilio_bot.py")
        self.transport = pillar2_twilio.build_twilio_transport(
            websocket=websocket,
            stream_sid=stream_sid,
            vad_analyzer=_build_vad_analyzer()
        )

    def get_pipecat_transport(self) -> Any:
        return self.transport


class LiveKitTransportAdapter(PipecatTransportAdapter):
    """Implementation for LiveKit WebRTC."""

    def __init__(self, room_url: str, bot_name: str):
        if not room_url:
            raise ValueError("LIVEKIT_URL is not set")
            
        from livekit import api
        from app.config import LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_ROOM
        
        # Generate token
        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity("voice-agent-bot")
            .with_name(bot_name)
            .with_grants(api.VideoGrants(room_join=True, room=LIVEKIT_ROOM))
            .to_jwt()
        )

        # Call Pillar_2 factory
        pillar2_livekit = _import_pillar2_module("pillar2_livekit", "livekit_bot.py")
        self.transport = pillar2_livekit.build_livekit_transport(
            room_url=room_url,
            token=token,
            room_name=LIVEKIT_ROOM,
            vad_analyzer=_build_vad_analyzer()
        )

    def get_pipecat_transport(self) -> Any:
        return self.transport


class MockWebSocketTransport(PipecatTransportAdapter):
    """Mock implementation for testing."""
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def get_pipecat_transport(self) -> Any:
        return {"type": "websocket", "config": self.kwargs}


class MockWebRTCTransport(PipecatTransportAdapter):
    """Mock implementation for testing."""
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def get_pipecat_transport(self) -> Any:
        return {"type": "webrtc", "config": self.kwargs}


