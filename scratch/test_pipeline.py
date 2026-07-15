import asyncio
import os
import time
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import LLMRunFrame
from app.adapters.pipecat.factory import PipecatFactory
from app.pipeline.builder import PipelineBuilder
from app.pipeline.factory import PipelineFactory
from app.events.bus import EventBus

async def run_test():
    event_bus = EventBus()
    await event_bus.start()
    
    pipeline_builder = PipelineFactory.create_voice_pipeline(
        event_bus=event_bus,
        session_id="test-session",
    )
    pipeline_model = pipeline_builder.build()
    
    # We will use the PipecatAdapter with Mock transport
    from app.adapters.pipecat.transport import PipecatTransportAdapter
    class DummyTransport(PipecatTransportAdapter):
        def __init__(self):
            from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
            self.t = LocalAudioTransport(LocalAudioTransportParams(audio_in_enabled=False, audio_out_enabled=False))
        def get_pipecat_transport(self):
            return self.t

    transport = DummyTransport()
    
    adapter = PipecatFactory.create_adapter(
        pipeline=pipeline_model,
        event_bus=event_bus,
        session_id="test-session",
        execution_id="test-exec",
        transport=transport,
    )
    
    # We manually simulate client connected
    async def simulate_client():
        await asyncio.sleep(2.0)
        logger.info("Simulating client connection and sending LLMRunFrame")
        from pipecat.frames.frames import LLMMessagesAppendFrame, LLMRunFrame
        from pipecat.processors.aggregators.llm_response_universal import LLMContext
        
        # We queue LLMRunFrame directly to the task
        await adapter.task.queue_frames([LLMRunFrame()])
        
        # wait 10 seconds to see if it generates anything
        await asyncio.sleep(10.0)
        import sys
        sys.exit(0)
        
    asyncio.create_task(simulate_client())
    await adapter.run()

if __name__ == "__main__":
    asyncio.run(run_test())
