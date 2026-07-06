"""
Real-Time Voice Pipeline — Unified Entry Point

Wires together Pillar 1 (orchestration) and Pillar 2 (real audio services):

    Daily.co (WebRTC mic)
        ↓
    DeepgramSTTService (nova-2)
        ↓
    GroqLLMService (llama3-8b-8192)
        ↓
    ElevenLabsTTSService
        ↓
    Daily.co (WebRTC speaker)

Each stage drives the ConversationStateMachine and publishes typed events
to the EventBus so the entire system is observable from a single stream.

Usage:
    python -m app.main
"""

import asyncio
import uuid

from loguru import logger

from app.config import DAILY_ROOM_URL, BOT_NAME
from app.conversation.state_machine import ConversationStateMachine
from app.conversation.transitions import ConversationState
from app.events.bus import EventBus
from app.events.event_types import SessionCreated, SessionClosed
from app.pipeline.factory import PipelineFactory
from app.session.manager import SessionManager
from app.session.state import SessionState

from app.adapters.pipecat.factory import PipecatFactory
from app.adapters.pipecat.transport import DailyTransportAdapter


async def run_voice_session() -> None:
    """Bootstrap and execute a single real-time voice session."""

    # ── 1. Session ──────────────────────────────────────────────────────
    session_manager = SessionManager()
    session = session_manager.create_session()
    session_id = session.session_id
    logger.info("Session created | session_id={sid}", sid=session_id)

    # ── 2. Event Bus ────────────────────────────────────────────────────
    event_bus = EventBus()
    await event_bus.start()
    event_bus.publish_sync(SessionCreated(session_id=session_id))
    logger.info("EventBus started")

    # ── 3. Conversation FSM ─────────────────────────────────────────────
    fsm = ConversationStateMachine(session_id=session_id)
    # Transition from IDLE → LISTENING (pipeline is about to start)
    fsm.transition_to(ConversationState.LISTENING, reason="session initialized")

    # ── 4. Pipeline DAG ─────────────────────────────────────────────────
    pipeline_builder = PipelineFactory.create_voice_pipeline(
        event_bus=event_bus,
        session_id=session_id,
    )
    pipeline = pipeline_builder.build()
    logger.info("Pipeline DAG built | pipeline_id={pid}", pid=pipeline.pipeline_id)

    # ── 5. Daily.co Transport (Pillar 2) ────────────────────────────────
    transport = DailyTransportAdapter(
        room_url=DAILY_ROOM_URL,
        bot_name=BOT_NAME,
    )
    transport.register_events()
    logger.info("DailyTransportAdapter ready | room={r}", r=DAILY_ROOM_URL)

    # ── 6. Execution UUID ───────────────────────────────────────────────
    execution_id = str(uuid.uuid4())

    # ── 7. Pipecat Adapter (glues DAG + real services + FSM) ───────────
    adapter = PipecatFactory.create_adapter(
        pipeline=pipeline,
        event_bus=event_bus,
        session_id=session_id,
        execution_id=execution_id,
        transport=transport,
        fsm=fsm,
    )
    logger.info("PipecatAdapter ready | execution_id={eid}", eid=execution_id)

    # ── 8. Update session state ─────────────────────────────────────────
    session_manager.set_state(session_id, SessionState.LISTENING)

    # ── 9. Run ──────────────────────────────────────────────────────────
    try:
        logger.info("Starting pipeline — join your Daily room and speak.")
        await adapter.run()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — shutting down gracefully")

    except Exception as exc:
        logger.exception("Pipeline error: {e}", e=exc)
        raise

    finally:
        # ── Cleanup ────────────────────────────────────────────────────
        try:
            fsm.close(reason="pipeline finished")
        except Exception:
            pass  # already closed or invalid state — ignore

        session_manager.set_state(session_id, SessionState.CLOSED)
        event_bus.publish_sync(SessionClosed(session_id=session_id))

        await event_bus.stop()
        logger.info("Session closed | session_id={sid}", sid=session_id)


def main() -> None:
    """Synchronous entry point."""
    asyncio.run(run_voice_session())


if __name__ == "__main__":
    main()
