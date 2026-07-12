import pytest
from unittest.mock import patch, MagicMock

from app.adapters.pipecat.transport import (
    MockWebSocketTransport,
    MockWebRTCTransport,
    LiveKitTransportAdapter
)


def test_mock_websocket_transport():
    transport = MockWebSocketTransport(port=8080)
    pipecat_trans = transport.get_pipecat_transport()
    assert pipecat_trans["type"] == "websocket"
    assert pipecat_trans["config"]["port"] == 8080


def test_mock_webrtc_transport():
    transport = MockWebRTCTransport(room="test")
    pipecat_trans = transport.get_pipecat_transport()
    assert pipecat_trans["type"] == "webrtc"
    assert pipecat_trans["config"]["room"] == "test"


@patch("app.config.LIVEKIT_URL", None)
def test_livekit_transport_missing_url():
    """Test ValueError when LIVEKIT_URL is missing."""
    import sys
    sys.modules['pipecat'] = MagicMock()
    sys.modules['pipecat.transports'] = MagicMock()
    sys.modules['pipecat.transports.livekit'] = MagicMock()
    sys.modules['pipecat.transports.livekit.transport'] = MagicMock()

    sys.modules['pipecat.audio'] = MagicMock()
    sys.modules['pipecat.audio.vad'] = MagicMock()
    sys.modules['pipecat.audio.vad.silero'] = MagicMock()
    sys.modules['pipecat.audio.vad.vad_analyzer'] = MagicMock()
    
    with pytest.raises(ValueError, match="LIVEKIT_URL is not set"):
        LiveKitTransportAdapter(room_url=None, bot_name="bot")

    # cleanup
    for k in list(sys.modules.keys()):
        if k.startswith('pipecat'):
            del sys.modules[k]


