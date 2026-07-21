"""
Factory for creating Pipecat Adapters.
"""

from typing import Any, Optional

from app.events import EventBus
from app.pipeline.models import Pipeline
from .adapter import PipecatAdapter
from .transport import PipecatTransportAdapter


class PipecatFactory:
    """Factory to build configured Pipecat adapters."""

    @staticmethod
    def create_adapter(
        pipeline: Pipeline,
        event_bus: EventBus,
        session_id: str,
        execution_id: str,
        transport: Optional[PipecatTransportAdapter] = None,
        fsm: Optional[Any] = None,
        latency_tracker: Optional[Any] = None,
        previous_summary: str = "",
    ) -> PipecatAdapter:
        """Create and return a configured PipecatAdapter.

        Args:
            pipeline:     The immutable Pipeline DAG to execute.
            event_bus:    Shared EventBus instance.
            session_id:   Session UUID.
            execution_id: Execution UUID for this run.
            transport:    Optional transport adapter (LiveKitTransportAdapter
                          in production, MockWebRTCTransport in tests).
            fsm:          Optional ConversationStateMachine.  When provided,
                          the adapter drives FSM state on each pipeline stage.
            latency_tracker: Optional tracker for latency metrics.
            previous_summary: Optional previous conversation summary.
        """
        return PipecatAdapter(
            pipeline=pipeline,
            event_bus=event_bus,
            session_id=session_id,
            execution_id=execution_id,
            transport=transport,
            fsm=fsm,
            latency_tracker=latency_tracker,
            previous_summary=previous_summary,
        )
