"""
Real-Time Voice Pipeline — Unified Entry Point

Supports Dual-Transport architecture:
1. Daily.co (WebRTC) for browser testing
2. Twilio (Telephony) for actual phone calls

Usage:
    python -m app.main
    (The app automatically launches FastAPI if TRANSPORT_MODE=twilio, 
     or runs directly as a CLI script if TRANSPORT_MODE is daily or livekit).
"""

import asyncio
import uuid
import sys
import os
import ssl
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
ssl._create_default_https_context = ssl._create_unverified_context

from loguru import logger
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse

from app.config import DAILY_ROOM_URL, LIVEKIT_URL, BOT_NAME, TRANSPORT_MODE
from app.conversation.state_machine import ConversationStateMachine
from app.conversation.transitions import ConversationState
from app.events.bus import EventBus
from app.events.event_types import SessionCreated, SessionClosed
from app.pipeline.factory import PipelineFactory
from app.session.manager import SessionManager
from app.session.state import SessionState

from app.adapters.pipecat.factory import PipecatFactory
from app.adapters.pipecat.transport import TwilioTransportAdapter


import time
global_timers = {}

# ── FastAPI App for Twilio ──────────────────────────────────────────────
app = FastAPI()

@app.post("/inbound-call")
async def handle_inbound_call(request: Request):
    """Twilio webhook endpoint. Returns TwiML to connect to our WebSocket."""
    global_timers["webhook_processing_start"] = time.perf_counter()
    logger.info("Incoming Twilio call received")
    
    # Resolve the host for the websocket stream
    host = request.headers.get("host", "localhost:8000")
    
    # If routed through ngrok, force secure websocket (wss)
    scheme = "wss" if "ngrok" in host or request.headers.get("x-forwarded-proto") == "https" else "ws"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{scheme}://{host}/ws" />
    </Connect>
</Response>
"""
    return HTMLResponse(content=twiml, media_type="application/xml")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Twilio WebSocket endpoint for Pipecat audio stream."""
    global_timers["media_stream_connection"] = time.perf_counter()
    await websocket.accept()
    logger.info("WebSocket connection accepted from Twilio")
    
    # Twilio sends a 'connected' event, then a 'start' event
    import json
    stream_sid = None
    
    # Wait for the start event
    for _ in range(5): # Don't loop forever
        data = await websocket.receive_text()
        msg = json.loads(data)
        if msg.get("event") == "start":
            stream_sid = msg["start"]["streamSid"]
            global_timers["first_audio_packet"] = time.perf_counter()
            logger.info(f"Twilio stream started: {stream_sid}")
            break
        elif msg.get("event") == "connected":
            logger.info("Twilio connected event received")
            continue
            
    if not stream_sid:
        logger.error("Did not receive 'start' event from Twilio")
        await websocket.close()
        return
    
    transport = TwilioTransportAdapter(websocket=websocket, stream_sid=stream_sid)
    
    # Block and run the voice session on this websocket
    await run_voice_session(transport=transport)


# ── Core Pipeline Session ───────────────────────────────────────────────
async def run_voice_session(transport=None) -> None:
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
    fsm.transition_to(ConversationState.LISTENING, reason="session initialized")

    # ── 4. Pipeline DAG ─────────────────────────────────────────────────
    pipeline_builder = PipelineFactory.create_voice_pipeline(
        event_bus=event_bus,
        session_id=session_id,
    )
    pipeline = pipeline_builder.build()
    logger.info("Pipeline DAG built | pipeline_id={pid}", pid=pipeline.pipeline_id)

    # ── 5. Transport Selection ──────────────────────────────────────────
    if not transport:
        if TRANSPORT_MODE.lower() == "livekit":
            from app.adapters.pipecat.transport import LiveKitTransportAdapter
            transport = LiveKitTransportAdapter(
                room_url=LIVEKIT_URL,
                bot_name=BOT_NAME,
            )
            # LiveKitTransport does not have a register_events method to call here
            logger.info("LiveKitTransportAdapter ready | room={r}", r=LIVEKIT_URL)
        else:
            raise ValueError(f"TRANSPORT_MODE '{TRANSPORT_MODE}' is invalid. Supported: 'twilio', 'livekit'.")
    else:
        logger.info("TwilioTransportAdapter injected via WebSocket.")

    # ── 6. Execution UUID ───────────────────────────────────────────────
    execution_id = str(uuid.uuid4())

    # ── 7. Pipecat Adapter ──────────────────────────────────────────────
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
        logger.info("Starting pipeline processing loop.")
        await adapter.run()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — shutting down gracefully")

    except Exception as exc:
        logger.exception("Pipeline error: {e}", e=exc)
        # Twilio websocket closure will throw exceptions, catch and swallow if normal
    finally:
        # ── Cleanup ────────────────────────────────────────────────────
        try:
            fsm.close(reason="pipeline finished")
        except Exception:
            pass 

        session_manager.set_state(session_id, SessionState.CLOSED)
        event_bus.publish_sync(SessionClosed(session_id=session_id))

        await event_bus.stop()
        logger.info("Session closed | session_id={sid}", sid=session_id)
        
        # Dump latency profiles
        import app.main
        for k, v in app.main.global_timers.items():
            logger.info(f"[LATENCY] {k} = {v}")
        app.main.global_timers.clear()


def main() -> None:
    """Synchronous entry point."""
    if TRANSPORT_MODE.lower() == "twilio":
        logger.info("TRANSPORT_MODE is set to 'twilio'. Starting FastAPI server...")
        import uvicorn
        # Run uvicorn server programmatically
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        logger.info("TRANSPORT_MODE is set to '{mode}'. Running standalone script...", mode=TRANSPORT_MODE)
        asyncio.run(run_voice_session())


if __name__ == "__main__":
    main()
