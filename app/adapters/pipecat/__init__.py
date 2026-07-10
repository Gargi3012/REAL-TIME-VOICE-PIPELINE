"""
Pipecat Adapter public API.
"""

from .adapter import PipecatAdapter
from .events import PipecatEventBridge
from .exceptions import (
    PipecatAdapterError,
    PipelineConversionError,
    ProcessorMappingError,
    RuntimeSynchronizationError,
    TransportMappingError,
)
from .factory import PipecatFactory
from .lifecycle import PipecatLifecycleManager
from .mapper import PipecatPipelineMapper
from .processors import PipecatProcessorAdapter
from .transport import (
    LiveKitTransportAdapter,
    MockWebRTCTransport,
    MockWebSocketTransport,
    PipecatTransportAdapter,
    TwilioTransportAdapter,
)
from .utils import extract_pipecat_metadata

__all__ = [
    "PipecatAdapter",
    "PipecatEventBridge",
    "PipecatFactory",
    "PipecatLifecycleManager",
    "PipecatPipelineMapper",
    "PipecatProcessorAdapter",
    "PipecatTransportAdapter",
    "LiveKitTransportAdapter",
    "TwilioTransportAdapter",
    "MockWebSocketTransport",
    "MockWebRTCTransport",
    "extract_pipecat_metadata",
    "PipecatAdapterError",
    "ProcessorMappingError",
    "TransportMappingError",
    "PipelineConversionError",
    "RuntimeSynchronizationError",
]
