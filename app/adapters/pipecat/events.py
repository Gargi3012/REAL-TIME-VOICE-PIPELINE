"""
Event mapping from Pipecat to our Event Bus.

PipecatEventBridge has two responsibilities:
1. Publish typed EventBus events (existing behaviour — unchanged).
2. Drive the ConversationStateMachine at each pipeline stage transition
   (new in Pillar 2 integration).

The FSM parameter is optional so existing unit tests that construct
PipecatEventBridge without a state machine continue to work.
"""

from typing import Optional

from loguru import logger

from app.events import EventBus
from app.events.event_types import (
    AudioGenerationStarted,
    ConversationStarted,
    ConversationEnded,
    ConversationInterrupted,
    ListeningStarted,
    PipelineCompleted,
    PipelineFailed,
    PipelineStarted,
    ProcessorExecutionCompleted,
    ProcessorExecutionFailed,
    ProcessorExecutionStarted,
    ResponseGenerated,
    SpeakingFinished,
    SpeakingStarted,
    ThinkingStarted,
    TranscriptReady,
)
from app.events.event_types import (
    AssistantGreetingStarted,
    AssistantGreetingGenerated,
    AssistantGreetingTTSStarted,
    AssistantGreetingCompleted,
    ConversationReady,
)


class PipecatEventBridge:

    def __init__(
        self,
        event_bus: EventBus,
        session_id: str,
        execution_id: str,
        fsm: Optional[object] = None,  # ConversationStateMachine — typed as object to avoid circular import
    ) -> None:
        self._bus = event_bus
        self._session_id = session_id
        self._execution_id = execution_id
        self._fsm = fsm  # may be None in test environments
        self._greeting_complete = False

    # ── FSM helper ──────────────────────────────────────────────────────

    def _fsm_transition(self, target_state_name: str, reason: str) -> None:
        if self._fsm is None:
            return
        try:
            from app.conversation.transitions import ConversationState
            target = ConversationState[target_state_name]
            if getattr(self._fsm, "get_current_state", lambda: None)() == target:
                return
            self._fsm.transition_to(target, reason=reason)  # type: ignore[union-attr]
        except Exception as exc:
            logger.bind(session_id=self._session_id).warning(
                "FSM transition to {state} failed: {err}",
                state=target_state_name,
                err=exc,
            )

    # ── Existing pipeline-level callbacks (unchanged) ────────────────────

    def on_pipeline_started(self) -> None:
        self._fsm_transition("LISTENING", reason="pipeline started")
        self._bus.publish_sync(
            PipelineStarted(
                session_id=self._session_id,
                payload={"execution_id": self._execution_id},
            )
        )
        self._bus.publish_sync(
            ConversationStarted(session_id=self._session_id)
        )
        self._bus.publish_sync(
            ListeningStarted(session_id=self._session_id)
        )

    def on_pipeline_completed(self) -> None:
        self._fsm_transition("CLOSED", reason="pipeline completed")
        self._bus.publish_sync(
            PipelineCompleted(
                session_id=self._session_id,
                payload={"execution_id": self._execution_id},
            )
        )
        self._bus.publish_sync(
            ConversationEnded(session_id=self._session_id)
        )

    def on_pipeline_failed(self, error: Exception) -> None:
        self._bus.publish_sync(
            PipelineFailed(
                session_id=self._session_id,
                payload={"execution_id": self._execution_id, "error": str(error)},
            )
        )

    def on_processor_started(self, processor_name: str) -> None:
        self._bus.publish_sync(
            ProcessorExecutionStarted(
                session_id=self._session_id,
                payload={"processor_id": processor_name},
            )
        )

    def on_processor_completed(self, processor_name: str) -> None:
        self._bus.publish_sync(
            ProcessorExecutionCompleted(
                session_id=self._session_id,
                payload={"processor_id": processor_name},
            )
        )

    def on_processor_error(self, processor_name: str, error: Exception) -> None:
        self._bus.publish_sync(
            ProcessorExecutionFailed(
                session_id=self._session_id,
                payload={"processor_id": processor_name, "error": str(error)},
            )
        )
        logger.bind(session_id=self._session_id).error(
            "Pipecat processor {p} error: {e}", p=processor_name, e=error
        )

    # ── New Pillar 2 stage callbacks ──────────────────────────────────────
    # These are wired to real Pipecat frame callbacks in adapter.py.

    def on_transcript_ready(self, text: str) -> None:
        """Called when Deepgram emits a final TranscriptionFrame."""
        import time
        self._turn_start_time = time.perf_counter()
        self._fsm_transition("TRANSCRIBING", reason="deepgram transcript received")
        self._bus.publish_sync(
            TranscriptReady(
                session_id=self._session_id,
                payload={"text": text},
            )
        )
        # Immediately transition to THINKING — LLM is next
        self._fsm_transition("THINKING", reason="sending transcript to LLM")
        self._bus.publish_sync(
            ThinkingStarted(session_id=self._session_id)
        )

    def on_llm_response_started(self) -> None:
        """Called when the LLM (Groq) starts generating a response."""
        # If this was an AI-initiated greeting, we might still be in LISTENING
        if self._fsm:
            current_state = self._fsm.get_current_state().value
            if current_state == "listening":
                self._fsm_transition("THINKING", reason="AI-initiated greeting (no transcript)")
                self._bus.publish_sync(ThinkingStarted(session_id=self._session_id))
                
        self._fsm_transition("GENERATING_RESPONSE", reason="LLM started generating")

    def on_llm_response_ready(self, text: str) -> None:
        """Called when the LLM (Groq) finishes generating a response."""
        if not self._greeting_complete:
            self._bus.publish_sync(AssistantGreetingGenerated(session_id=self._session_id, payload={"text": text}))
            
        self._bus.publish_sync(
            ResponseGenerated(
                session_id=self._session_id,
                payload={"text": text},
            )
        )
        self._fsm_transition("GENERATING_AUDIO", reason="LLM response complete, starting TTS")
        self._bus.publish_sync(
            AudioGenerationStarted(session_id=self._session_id)
        )

    def on_audio_started(self) -> None:
        """Called when ElevenLabs begins streaming audio to the transport output."""
        import time
        latency_ms = 0
        if hasattr(self, "_turn_start_time") and self._turn_start_time:
            latency_ms = int((time.perf_counter() - self._turn_start_time) * 1000)

        if not self._greeting_complete:
            self._bus.publish_sync(AssistantGreetingTTSStarted(session_id=self._session_id))
            
        self._fsm_transition("SPEAKING", reason="TTS audio playback started")
        self._bus.publish_sync(
            SpeakingStarted(session_id=self._session_id, payload={"latency_ms": latency_ms, "total_latency_ms": latency_ms})
        )

    def on_audio_finished(self) -> None:
        """Called when the TTS audio frame stream is fully delivered."""
        self._bus.publish_sync(
            SpeakingFinished(session_id=self._session_id)
        )
        
        if not self._greeting_complete:
            self._greeting_complete = True
            self._bus.publish_sync(AssistantGreetingCompleted(session_id=self._session_id))
            self._bus.publish_sync(ConversationReady(session_id=self._session_id))
            
        # Loop back to LISTENING for the next user turn
        self._fsm_transition("LISTENING", reason="audio playback complete — ready for next turn")
        self._bus.publish_sync(
            ListeningStarted(session_id=self._session_id)
        )

    def on_user_interrupted(self) -> None:
        """Called when user speech is detected during AI audio playback (barge-in)."""
        self._fsm_transition("INTERRUPTED", reason="user barged in")
        self._bus.publish_sync(
            ConversationInterrupted(session_id=self._session_id)
        )
        # Resolve interruption back to listening
        self._fsm_transition("LISTENING", reason="resuming listening after interruption")
        self._bus.publish_sync(
            ListeningStarted(session_id=self._session_id)
        )
