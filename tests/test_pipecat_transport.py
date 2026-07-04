import pytest
from unittest.mock import patch, MagicMock

from app.adapters.pipecat.transport import (
    MockWebSocketTransport,
    MockWebRTCTransport,
    DailyTransportAdapter
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


@patch("app.config.DAILY_ROOM_URL", None)
def test_daily_transport_missing_url():
    """Test ValueError when DAILY_ROOM_URL is missing."""
    import sys
    from unittest.mock import MagicMock
    sys.modules['pipecat'] = MagicMock()
    sys.modules['pipecat.transports'] = MagicMock()
    sys.modules['pipecat.transports.services'] = MagicMock()
    sys.modules['pipecat.transports.services.daily'] = MagicMock()
    sys.modules['pipecat.vad'] = MagicMock()
    sys.modules['pipecat.vad.silero'] = MagicMock()
    sys.modules['pipecat.vad.vad_analyzer'] = MagicMock()
    
    with pytest.raises(ValueError, match="DAILY_ROOM_URL is not set"):
        DailyTransportAdapter(room_url=None)
    
    # cleanup
    for k in list(sys.modules.keys()):
        if k.startswith('pipecat'):
            del sys.modules[k]


def test_daily_transport_imports_pipecat():
    """Test importing pipecat throws ImportError in CI environments without it."""
    with pytest.raises(ImportError):
        DailyTransportAdapter(room_url="https://test.daily.co/room")
