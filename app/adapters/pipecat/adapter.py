"""
Main Pipecat Adapter.

In production (pipecat-ai installed):
    Uses real pipecat.pipeline.Pipeline / PipelineTask / PipelineRunner.
    Wires transport input/output at the front and back of the
    processor array, and attaches PipecatEventBridge frame callbacks so
    every stage drives the ConversationStateMachine and EventBus.

In test environments (pipecat-ai not installed):
    Falls back to MockPipecatPipelineTask (unchanged from Milestone 7)
    so all existing tests continue to pass without modification.
"""

import asyncio
import time
from typing import Any, List, Optional

from loguru import logger

from app.events import EventBus
from app.pipeline.models import Pipeline
from .events import PipecatEventBridge
from .exceptions import PipecatAdapterError
from .lifecycle import PipecatLifecycleManager
from .mapper import PipecatPipelineMapper
from .transport import PipecatTransportAdapter


# ── Fallback mock (kept for test compatibility) ───────────────────────

class MockPipecatPipelineTask:
    """Mock stand-in used when pipecat-ai is not installed."""

    def __init__(self, processors: List[Any], event_handler: Any = None) -> None:
        self.processors = processors
        self.event_handler = event_handler
        self._running = False

    async def start(self) -> None:
        self._running = True
        if self.event_handler:
            self.event_handler.on_pipeline_started()

    async def wait(self) -> None:
        while self._running:
            await asyncio.sleep(0.1)

    async def stop(self) -> None:
        self._running = False
        if self.event_handler:
            self.event_handler.on_pipeline_completed()


# ── Real pipeline task builder ────────────────────────────────────────

def _build_real_pipeline_task(
    pipecat_processors: List[Any],
    transport: Optional[PipecatTransportAdapter],
    bridge: PipecatEventBridge,
) -> Any:
    """Build an actual pipecat.pipeline.task.PipelineTask.

    Injects transport.input() at the start and transport.output() at the
    end of the processor list, then wires frame-level callbacks from the
    bridge so every stage event flows into the EventBus and FSM.

    Raises ImportError if pipecat-ai is not installed.
    """
    from pipecat.pipeline.pipeline import Pipeline as PipecatPipeline
    from pipecat.pipeline.task import PipelineTask
    from pipecat.frames.frames import TranscriptionFrame, LLMFullResponseEndFrame, TTSStartedFrame, TTSStoppedFrame, UserStartedSpeakingFrame

    processors: List[Any] = []

    # 1. Transport input (mic audio) at the front
    if transport is not None:
        real_transport = transport.get_pipecat_transport()
        processors.append(real_transport.input())
        
        # In Pipecat 1.5.0, VAD is a separate processor that must be injected manually
        from pipecat.processors.audio.vad_processor import VADProcessor
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        processors.append(VADProcessor(vad_analyzer=SileroVADAnalyzer()))

    # 2. Core processors (STT → LLM → TTS) from the mapper
    # We must wire up the OpenAILLMContext and aggregator for the LLM
    from pipecat.services.groq.llm import GroqLLMService
    from pipecat.pipeline.pipeline import Pipeline as PipecatPipeline
    
    # We need to find the LLM to attach the aggregator
    llm = next((p for p in pipecat_processors if isinstance(p, GroqLLMService)), None)
    
    if llm:
        from pipecat.processors.aggregators.llm_context import LLMContext
        from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregator, LLMAssistantAggregator
        
        from pipecat.turns.user_turn_strategies import UserTurnStrategies
        from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
        from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregatorParams

        context = LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful and friendly AI assistant. Keep responses short and conversational."
                }
            ]
        )
        
        # Optimize Turn Stop Strategy for extreme low latency (bypasses LLM completeness checks)
        from pipecat.turns.user_mute.mute_until_first_bot_complete_user_mute_strategy import MuteUntilFirstBotCompleteUserMuteStrategy
        import os
        
        mute_strategies = []
        if os.getenv("ENABLE_INITIAL_GREETING", "True").lower() == "true":
            mute_strategies.append(MuteUntilFirstBotCompleteUserMuteStrategy())
            
        agg_params = LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.6)]
            ),
            user_mute_strategies=mute_strategies
        )
        user_agg = LLMUserAggregator(context, params=agg_params)
        asst_agg = LLMAssistantAggregator(context)
        
        # Build the exact Pipecat sequence: [stt, user_agg, llm, tts, asst_agg]
        new_processors = []
        for p in pipecat_processors:
            if isinstance(p, GroqLLMService):
                new_processors.append(user_agg)
                new_processors.append(p)
            elif p.__class__.__name__.endswith("TTSService"):
                new_processors.append(p)
                new_processors.append(asst_agg)
            else:
                new_processors.append(p)
                
        processors.extend(new_processors)
    else:
        processors.extend(pipecat_processors)

    # 3. Transport output (speaker) at the back
    if transport is not None:
        real_transport = transport.get_pipecat_transport()
        processors.append(real_transport.output())

    real_pipeline = PipecatPipeline(processors)
    from pipecat.observers.base_observer import BaseObserver, FramePushed

    class EventBridgeObserver(BaseObserver):
        async def on_push_frame(self, data: FramePushed):
            from app.main import global_timers
            frame = data.frame
            now = time.perf_counter()
            from pipecat.frames.frames import (
                TranscriptionFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame, 
                TTSStartedFrame, TTSStoppedFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame
            )
            
            if isinstance(frame, UserStartedSpeakingFrame):
                if "vad_user_started" not in global_timers:
                    global_timers["vad_user_started"] = now
                bridge.on_user_interrupted()
                
            elif isinstance(frame, UserStoppedSpeakingFrame):
                global_timers["vad_user_stopped"] = now
                
            elif isinstance(frame, TranscriptionFrame) and frame.text:
                if "stt_first_transcript" not in global_timers:
                    global_timers["stt_first_transcript"] = now
                bridge.on_transcript_ready(frame.text)
                
            elif isinstance(frame, LLMFullResponseStartFrame):
                if "llm_first_token" not in global_timers:
                    global_timers["llm_first_token"] = now
                bridge.on_llm_response_started()
                    
            elif isinstance(frame, LLMFullResponseEndFrame):
                global_timers["llm_complete"] = now
                bridge.on_llm_response_ready(getattr(frame, "text", ""))
                
            elif isinstance(frame, TTSStartedFrame):
                bridge.on_audio_started()
                
            elif isinstance(frame, TTSStoppedFrame):
                bridge.on_audio_finished()

    task = PipelineTask(real_pipeline, observers=[EventBridgeObserver()])
    return task


# ── Main adapter ─────────────────────────────────────────────────────

class PipecatAdapter:
    """Executes a framework-independent Pipeline using the Pipecat runtime."""

    def __init__(
        self,
        pipeline: Pipeline,
        event_bus: EventBus,
        session_id: str,
        execution_id: str,
        transport: Optional[PipecatTransportAdapter] = None,
        fsm: Optional[Any] = None,
    ) -> None:
        self.pipeline = pipeline
        self.event_bus = event_bus
        self.session_id = session_id
        self.execution_id = execution_id
        self.transport = transport

        # Bridge is created with the optional FSM — None is fine for tests
        self.bridge = PipecatEventBridge(event_bus, session_id, execution_id, fsm=fsm)
        self.task: Any = None
        self.lifecycle: Optional[PipecatLifecycleManager] = None

        self._build_task()

    def _build_task(self) -> None:
        """Build the Pipecat pipeline task (real or mock, depending on environment)."""
        try:
            logger.bind(
                session_id=self.session_id,
                execution_id=self.execution_id,
            ).info("Building Pipecat adapter task")

            # 1. Map internal DAG processors (transport roles excluded — handled separately)
            processor_adapters = PipecatPipelineMapper.map_pipeline(self.pipeline)
            # Filter out placeholder transport processors — the real ones come from the injected transport
            pipecat_processors = [
                p.get_processor()
                for p in processor_adapters
                if not getattr(p.get_processor(), "name", "").startswith("Transport_")
            ]

            # 2. Try to build a real PipelineTask; fall back to mock on ImportError or Mock transport
            try:
                if self.transport and "Mock" in type(self.transport).__name__:
                    raise ImportError("Force mock fallback for tests")
                if any("Mock" in type(p).__name__ for p in pipecat_processors):
                    raise ImportError("Force mock fallback for tests because mock processors exist")
                self.task = _build_real_pipeline_task(
                    pipecat_processors, self.transport, self.bridge
                )
                logger.bind(session_id=self.session_id).info(
                    "Real pipecat PipelineTask created"
                )
            except ImportError as e:
                logger.exception(e)
                logger.bind(session_id=self.session_id).warning(
                    "pipecat-ai not installed — using MockPipecatPipelineTask"
                )
                if self.transport:
                    real_t = self.transport.get_pipecat_transport()
                    pipecat_processors.insert(0, real_t)
                self.task = MockPipecatPipelineTask(
                    processors=pipecat_processors,
                    event_handler=self.bridge,
                )

            self.lifecycle = PipecatLifecycleManager(self.task, self.session_id)

        except Exception as e:
            self.bridge.on_pipeline_failed(e)
            raise PipecatAdapterError(f"Failed to build Pipecat adapter task: {e}") from e

    async def run(self) -> None:
        """Execute the pipeline using Pipecat."""
        if not self.lifecycle:
            raise PipecatAdapterError("Adapter not fully initialized")

        try:
            logger.bind(
                session_id=self.session_id,
                execution_id=self.execution_id,
            ).info("Running Pipecat adapter")
            
            await self.lifecycle.start()
            
            import os
            import asyncio
            if os.getenv("ENABLE_INITIAL_GREETING", "True").lower() == "true":
                from pipecat.frames.frames import LLMMessagesAppendFrame
                from app.events.event_types import AssistantGreetingStarted
                
                logger.bind(session_id=self.session_id).info("Queueing initial AI greeting")
                
                self.event_bus.publish_sync(
                    AssistantGreetingStarted(session_id=self.session_id)
                )

                # Delay greeting to allow Twilio audio to fully connect
                await asyncio.sleep(2.0)
                await self.task.queue_frames([
                    LLMMessagesAppendFrame(
                        messages=[{
                            "role": "system",
                            "content": "A new phone conversation has just started. You are Sarah from Cybernauts Noida. Say exactly: 'Hello, I'm Sarah from Cybernauts Noida. How can I assist you?'"
                        }],
                        run_llm=True
                    )
                ])

            # For the mock task: manually simulate processor events
            if isinstance(self.task, MockPipecatPipelineTask):
                for proc in self.task.processors:
                    name = getattr(proc, "name", "unknown")
                    self.bridge.on_processor_started(name)
                    await asyncio.sleep(0.01)
                    self.bridge.on_processor_completed(name)
                await self.lifecycle.stop()
                await self.lifecycle.wait_until_done()
            else:
                from pipecat.pipeline.runner import PipelineRunner
                runner = PipelineRunner()
                await runner.run(self.task)

        except Exception as e:
            self.bridge.on_pipeline_failed(e)
            logger.bind(session_id=self.session_id).error(
                "Pipecat adapter execution failed: {e}", e=e
            )
            raise PipecatAdapterError(f"Execution failed: {e}") from e
