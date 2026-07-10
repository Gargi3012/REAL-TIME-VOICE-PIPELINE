"""
Transport abstractions for Pipecat.
"""

import abc
import os
import sys
from typing import Any
from fastapi import WebSocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

# Make Pillar-2 imports available
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../Pillar-2/app")))
from fastapi_websocket import FastAPIWebsocketTransport, FastAPIWebsocketParams


class PipecatTransportAdapter(abc.ABC):
    """Abstract interface for wrapping a Pipecat Transport."""

    @abc.abstractmethod
    def get_pipecat_transport(self) -> Any:
        """Return the underlying Pipecat transport instance."""
        pass


def _build_vad_analyzer():
    return SileroVADAnalyzer(
        params=VADParams(
            confidence=0.7,
            start_secs=0.2,
            stop_secs=0.5,
            min_volume=0.6,
        )
    )


class TwilioTransportAdapter(PipecatTransportAdapter):
    """Implementation for Twilio WebSockets."""

    def __init__(self, websocket: WebSocket, stream_sid: str):
        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            params=TwilioFrameSerializer.InputParams(
                twilio_sample_rate=8000,
                sample_rate=8000,
                auto_hang_up=False,
            ),
        )

        self.transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=8000,
                audio_out_sample_rate=8000,
                add_wav_header=False,
                vad_enabled=False,       # Disabled to prevent pipecat from calling finalize() on Deepgram
                vad_analyzer=_build_vad_analyzer(),
                serializer=serializer,
            ),
        )

    def get_pipecat_transport(self) -> Any:
        return self.transport


class LiveKitTransportAdapter(PipecatTransportAdapter):
    """Implementation for LiveKit WebRTC."""

    def __init__(self, room_url: str, bot_name: str):
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

        from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport

        self.transport = LiveKitTransport(
            url=room_url,
            token=token,
            room_name=LIVEKIT_ROOM,
            params=LiveKitParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_enabled=False,       # Disabled to prevent pipecat from calling finalize() on Deepgram
                vad_analyzer=_build_vad_analyzer(),
                # Bot's own TTS output can be interrupted the instant user audio crosses the VAD threshold above.
                audio_out_is_live=True,
            ),
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


