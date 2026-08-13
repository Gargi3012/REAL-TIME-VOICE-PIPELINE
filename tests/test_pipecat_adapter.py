"""
Tests for Pipecat Adapter.
"""

import pytest
from unittest.mock import patch

from app.events import EventBus
from app.pipeline.builder import PipelineBuilder
from app.pipeline.processors import ProcessorNode, ProcessorRole
from app.pipeline.models import Pipeline
from app.adapters.pipecat import (
    PipecatAdapter,
    MockWebSocketTransport,
    PipecatAdapterError
)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()

@pytest.fixture
def pipeline(bus: EventBus) -> Pipeline:
    builder = PipelineBuilder(bus, "session1")
    builder.add_processor(ProcessorNode("STT", ProcessorRole.STT))
    builder.add_processor(ProcessorNode("LLM", ProcessorRole.LLM))
    builder.connect("STT", "LLM")
    return builder.build()


def test_adapter_initialization(bus: EventBus, pipeline: Pipeline) -> None:
    transport = MockWebSocketTransport()
    adapter = PipecatAdapter(pipeline, bus, "session1", "exec1", transport)
    
    assert adapter.task is not None
    assert adapter.lifecycle is not None
    assert len(adapter.task.processors) == 3 # transport + STT + LLM


def test_adapter_initialization_failure(bus: EventBus, monkeypatch: pytest.MonkeyPatch) -> None:
    bad_pipeline = Pipeline(processors={}, graph={}, pipeline_id="p1")
    
    # Mock scheduler to trigger PipelineConversionError which triggers PipecatAdapterError
    monkeypatch.setattr("app.adapters.pipecat.mapper.PipelineScheduler.get_execution_order", lambda self: ["Missing"])
    
    with pytest.raises(PipecatAdapterError, match="Failed to build Pipecat adapter task"):
        PipecatAdapter(bad_pipeline, bus, "session1", "exec1")


@pytest.mark.asyncio
async def test_adapter_run_success(bus: EventBus, pipeline: Pipeline) -> None:
    adapter = PipecatAdapter(pipeline, bus, "session1", "exec1")
    
    with patch("pipecat.pipeline.runner.PipelineRunner.run") as mock_run:
        await adapter.run()
        if adapter.task.__class__.__name__ == "MockPipecatPipelineTask":
            assert mock_run.call_count == 0
        else:
            mock_run.assert_called_once()
        
    # If run completes without error, it succeeded.
    # Check that events were fired
    assert bus._queue.qsize() > 0



@pytest.mark.asyncio
async def test_adapter_run_uninitialized() -> None:
    # A bit hacky to test uninitialized, but we can set lifecycle to None
    bus = EventBus()
    builder = PipelineBuilder(bus, "session1")
    builder.add_processor(ProcessorNode("STT", ProcessorRole.STT))
    pipeline = builder.build()
    
    adapter = PipecatAdapter(pipeline, bus, "session1", "exec1")
    adapter.lifecycle = None
    
    with pytest.raises(PipecatAdapterError, match="Adapter not fully initialized"):
        await adapter.run()


@pytest.mark.asyncio
async def test_adapter_run_failure(bus: EventBus, pipeline: Pipeline) -> None:
    adapter = PipecatAdapter(pipeline, bus, "session1", "exec1")
    
    # Intentionally corrupt the lifecycle manager to throw an error on start
    async def bad_start() -> None:
        raise ValueError("Simulated Pipecat Crash")
        
    adapter.lifecycle.start = bad_start # type: ignore
    
    with pytest.raises(PipecatAdapterError, match="Execution failed"):
        await adapter.run()
