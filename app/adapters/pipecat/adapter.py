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
import os
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
from app.llm.prompts import VOICE_SYSTEM_PROMPT
from app.llm.company_faq import get_faq_context_block


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
    """Build an actual pipecat.pipeline.task.PipelineTask directly from mapped processors.

    Injects transport.input() at the start and transport.output() at the
    end of the processor list, then wires frame-level callbacks from the
    bridge so every stage event flows into the EventBus and FSM.

    Raises ImportError if pipecat-ai is not installed.
    """
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMUserAggregator,
        LLMAssistantAggregator,
    )
    from pipecat.observers.base_observer import BaseObserver, FramePushed
    import time

    # 1. Prepare context for Pillar 3 FAQ & Caller Persistence
    session_id = bridge._session_id
    from app.session.manager import SessionManager
    sm = SessionManager()
    sess = sm.get_session(session_id)
    prev_summary = sess.metadata.get("previous_summary", "") if sess else ""

    company_context = get_faq_context_block()
    if prev_summary:
        company_context += "\n\nPrevious Conversation Summary for this caller:\n" + prev_summary

    prompt = VOICE_SYSTEM_PROMPT
    if company_context:
        prompt += f"\n\nCompany Context:\n{company_context}"
    context = LLMContext([{"role": "system", "content": prompt}])

    # 2. Extract real transport
    real_transport = transport.get_pipecat_transport() if transport else None

    # 3. Create EventBridgeObserver to connect Pipecat to EventBus (Pillar 1)
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

            elif isinstance(frame, TranscriptionFrame) and getattr(frame, "text", ""):
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

    # 4. Build task using mapped processors — use endswith() to avoid
    #    substring collision (e.g. "STT" is a substring of "STTService" and
    #    "TTSService" — naive "TTS" in name would match "DeepgramSTTService").
    stt = next(
        (p for p in pipecat_processors
         if type(p).__name__.endswith("STTService") or type(p).__name__ == "MockSTT"),
        None,
    )
    llm = next(
        (p for p in pipecat_processors
         if type(p).__name__.endswith("LLMService") or type(p).__name__ == "MockLLM"),
        None,
    )
    tts = next(
        (p for p in pipecat_processors
         if type(p).__name__.endswith("TTSService") or type(p).__name__ == "MockTTS"),
        None,
    )

    if not (stt and llm and tts):
        raise ValueError(f"Pipeline is missing processors. STT={stt}, LLM={llm}, TTS={tts}")

    logger.debug(f"Pipeline elements: STT={type(stt).__name__}, LLM={type(llm).__name__}, TTS={type(tts).__name__}")

    # Optimize Turn Stop Strategy for extreme low latency (bypasses LLM completeness checks)
    from pipecat.turns.user_turn_strategies import UserTurnStrategies
    from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
    from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregatorParams
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

    # Pipecat 1.5.0: create_context_aggregator() was removed from LLM services.
    # Directly instantiate the user/assistant aggregators paired together.
    user_aggregator = LLMUserAggregator(context=context, params=agg_params)
    assistant_aggregator = LLMAssistantAggregator(
        context=context,
        _paired_user_aggregator=user_aggregator,
    )

    # In Pipecat 1.5.0, VAD is a separate processor that must be injected manually
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.audio.vad.silero import SileroVADAnalyzer

    # Canonical Pipecat voice pipeline order:
    #   transport.input → VADProcessor → STT → user_aggregator → LLM → TTS → transport.output → assistant_aggregator
    pipeline_elements = [
        real_transport.input(),
        VADProcessor(vad_analyzer=SileroVADAnalyzer()),
        stt,
        user_aggregator,
        llm,
        tts,
        real_transport.output(),
        assistant_aggregator,
    ]

    pipeline = Pipeline(pipeline_elements)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[EventBridgeObserver()],
    )

    return task


# ── Main adapter ─────────────────────────────────────────────────────
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

            # ── Mock path (tests only) ────────────────────────────────────
            if isinstance(self.task, MockPipecatPipelineTask):
                await self.lifecycle.start()
                for proc in self.task.processors:
                    name = getattr(proc, "name", "unknown")
                    self.bridge.on_processor_started(name)
                    await asyncio.sleep(0.01)
                    self.bridge.on_processor_completed(name)
                await self.lifecycle.stop()
                await self.lifecycle.wait_until_done()
                return

            # ── Real Pipecat 1.5.0 path ───────────────────────────────────
            #
            # GREETING STRATEGY:
            # Use TTSSpeakFrame — the canonical Pipecat idiom for bot-initiated
            # speech.  It bypasses the LLM entirely and goes straight to ElevenLabs
            # TTS.  This removes LLM latency and any risk of a silent LLM drop.
            #
            # The frame is queued from a background asyncio.Task launched inside
            # on_client_connected.  The task sleeps 1.5s to guarantee StartFrame has
            # fully propagated through every processor before we inject speech.
            # queue_frames() puts the frame in _push_queue which is drained in-order,
            # so the TTSSpeakFrame always arrives after StartFrame is done.
            from pipecat.pipeline.runner import PipelineRunner
            from pipecat.frames.frames import TTSSpeakFrame
            from app.events.event_types import AssistantGreetingStarted

            pipecat_transport = self.transport.get_pipecat_transport()
            enable_greeting = os.getenv("ENABLE_INITIAL_GREETING", "True").lower() == "true"
            task_ref = self.task  # captured for closure

            @pipecat_transport.event_handler("on_client_connected")
            async def on_client_connected(transport, websocket):
                logger.bind(session_id=self.session_id).info(
                    "Transport: client connected — launching greeting task"
                )
                if not enable_greeting:
                    return

                async def _send_greeting():
                    try:
                        logger.bind(session_id=self.session_id).info(
                            "Greeting task: sleeping 1.5s for pipeline to be fully ready..."
                        )
                        await asyncio.sleep(1.5)

                        logger.bind(session_id=self.session_id).info(
                            "Greeting task: queuing TTSSpeakFrame"
                        )
                        self.event_bus.publish_sync(
                            AssistantGreetingStarted(session_id=self.session_id)
                        )
                        await task_ref.queue_frames([
                            TTSSpeakFrame(
                                text=(
                                    "Hello! Thank you for calling Cybernauts Noida. "
                                    "I'm Sarah, your virtual assistant. "
                                    "How can I help you today?"
                                ),
                                append_to_context=True,
                            )
                        ])
                        logger.bind(session_id=self.session_id).info(
                            "Greeting task: TTSSpeakFrame queued successfully ✓"
                        )
                    except Exception as greet_err:
                        logger.bind(session_id=self.session_id).exception(
                            "Greeting task failed: {e}", e=greet_err
                        )

                # Fire and forget — do not block the transport event callback
                asyncio.create_task(_send_greeting())

            runner = PipelineRunner()
            logger.bind(session_id=self.session_id).info(
                "Starting PipelineRunner with task"
            )
            await runner.run(self.task)

        except Exception as e:
            self.bridge.on_pipeline_failed(e)
            logger.bind(session_id=self.session_id).exception(
                "Pipecat adapter execution failed: {e}", e=e
            )
            raise PipecatAdapterError(f"Execution failed: {e}") from e
