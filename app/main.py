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
from fastapi.websockets import WebSocketDisconnect

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
    
    # Extract phone number
    form_data = await request.form()
    phone_number = form_data.get("From", "unknown_client")
    import urllib.parse
    phone_encoded = urllib.parse.quote(phone_number)
    
    # ── Database Pre-fetch (P1 Fix) ─────────────────────────────────────
    from app.db.connection import db_manager
    from app.repositories.client_repository import ClientRepository
    from app.repositories.session_repository import SessionRepository

    client_id_str = ""
    previous_summary = ""

    try:
        async with db_manager.get_session() as db:
            client = await ClientRepository.get_or_create_client(db, phone_number)
            client_id_str = str(client.id)
            
            summary_text = await SessionRepository.get_summary(db, client.id)
            if summary_text:
                previous_summary = summary_text
    except Exception as e:
        logger.error(f"Failed DB pre-fetch: {e}")

    # Resolve the host for the websocket stream
    host = request.headers.get("host", "localhost:8000")
    
    # If routed through ngrok, force secure websocket (wss)
    scheme = "wss" if "ngrok" in host or request.headers.get("x-forwarded-proto") == "https" else "ws"

    company_context = request.query_params.get("company_context", "")
    context_encoded = urllib.parse.quote(company_context) if company_context else ""
    
    stream_url = f"{scheme}://{host}/ws?phone={phone_encoded}&client_id={client_id_str}"
    
    if context_encoded:
        stream_url += f"&company_context={context_encoded}"
    if previous_summary:
        summary_encoded = urllib.parse.quote(previous_summary)
        stream_url += f"&previous_summary={summary_encoded}"
    
    # Escape ampersands for valid XML
    stream_url_xml = stream_url.replace("&", "&amp;")
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url_xml}" />
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
    
    # Extract params from URL query (P1 Fix)
    phone_number = websocket.query_params.get("phone", "unknown_client")
    client_id_str = websocket.query_params.get("client_id", "")
    company_context = websocket.query_params.get("company_context", "")
    previous_summary = websocket.query_params.get("previous_summary", "")
    
    # Block and run the voice session on this websocket
    await run_voice_session(
        transport=transport, 
        phone_number=phone_number, 
        company_context=company_context,
        client_id_str=client_id_str,
        previous_summary=previous_summary
    )


# ── Core Pipeline Session ───────────────────────────────────────────────
async def run_voice_session(
    transport=None, 
    phone_number: str = "unknown_client", 
    company_context: str = "",
    client_id_str: str = "",
    previous_summary: str = ""
) -> None:
    """Bootstrap and execute a single real-time voice session."""

    from app.db.connection import db_manager
    from app.repositories.session_repository import SessionRepository

    # ── 1. Session ──────────────────────────────────────────────────────
    session_manager = SessionManager()
    session = await session_manager.create_session(metadata={
        "client_id": client_id_str,
        "previous_summary": previous_summary,
        "company_context": company_context
    })
    session_id = session.session_id
    logger.info("Session created | session_id={sid} | client={client}", sid=session_id, client=phone_number)
    
    # Persist the Session in DB
    if client_id_str:
        try:
            c_id = uuid.UUID(client_id_str)
            async with db_manager.get_session() as db:
                await SessionRepository.create_session(db, session_id, c_id)
        except Exception as e:
            logger.error(f"Failed to persist Session: {e}")

    # ── 2. Event Bus ────────────────────────────────────────────────────
    event_bus = EventBus()
    
    # Subscribe to SessionClosed for DB Persistence
    async def on_session_closed(event: SessionClosed) -> None:
        async with db_manager.get_session() as db_session:
            sess_data = await session_manager.get_session(event.session_id)
            if not sess_data:
                return
            
            c_id_str = sess_data.metadata.get("client_id")
            if c_id_str:
                c_id = uuid.UUID(c_id_str)
                
                # Mock LLM Summary Generation (in real prod, call an LLM API here with transcript)
                # Real LLM Summary Generation — combines previous summary + this call's
                # transcript into one updated, concise summary (overwrites the old one).
                from app.llm.client import GroqLLMClient
                from app.session.message import Message

                history_texts = [
                    f"{msg.role}: {msg.content}"
                    for msg in sess_data.history
                    if msg.role != "system"
                ]
                transcript = "\n".join(history_texts)

                prev_summary_text = sess_data.metadata.get("previous_summary", "")

                summary_prompt = (
                    "You are maintaining a running memory of a caller for a voice assistant. "
                    "Combine the previous summary with the new call transcript below into ONE "
                    "updated summary. Keep it concise (3-5 sentences), factual, and focused on "
                    "details useful for future calls (who they are, what they asked about, any "
                    "preferences or unresolved issues). Do not include greetings or small talk.\n\n"
                    f"Previous summary:\n{prev_summary_text if prev_summary_text else '(none, first call)'}\n\n"
                    f"New call transcript:\n{transcript if transcript else '(no conversation recorded)'}"
                )

                try:
                    summary_client = GroqLLMClient()
                    summary_messages = [
                        Message(role="system", content="You write concise caller memory summaries."),
                        Message(role="user", content=summary_prompt),
                    ]
                    generated_summary = ""
                    async for chunk in summary_client.stream_response(summary_messages):
                        generated_summary += chunk
                    generated_summary = generated_summary.strip()
                    if not generated_summary:
                        generated_summary = prev_summary_text  # fallback: keep old summary
                except Exception as summary_err:
                    logger.error(
                        "Summary generation failed for session {sid}: {err}",
                        sid=event.session_id, err=summary_err,
                    )
                    generated_summary = prev_summary_text  # fallback: don't lose old summary on failure

                await SessionRepository.save_summary(db_session, c_id, generated_summary)
                await SessionRepository.close_session(db_session, event.session_id, int(sess_data.duration_seconds))
                logger.info("Persisted call summary and closed DB session for {sid}", sid=event.session_id)

    await event_bus.subscribe("SessionClosed", on_session_closed)
                
    await event_bus.subscribe(SessionClosed.__name__, on_session_closed)
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
    await session_manager.set_state(session_id, SessionState.LISTENING)

    # ── 9. Run ──────────────────────────────────────────────────────────
    try:
        logger.info("Starting pipeline processing loop.")
        # P0 Fix: Enforce wait_for to prevent infinite hangs if supported, or just catch disconnects
        await adapter.run()

    except WebSocketDisconnect:
        logger.warning("Twilio WebSocket disconnected abruptly.")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — shutting down gracefully")
    except Exception as exc:
        logger.exception("Pipeline error: {e}", e=exc)
    finally:
        # P0 Fix: Zombie Pipeline Cleanup
        # If the adapter is still running, ensure it's stopped.
        # Pipecat pipeline task cancellation logic here if needed.
        logger.info("Executing pipeline cleanup.")

        try:
            fsm.close(reason="pipeline finished")
        except Exception:
            pass 

        await session_manager.set_state(session_id, SessionState.CLOSED)
        event_bus.publish_sync(SessionClosed(session_id=session_id))
        await event_bus._queue.join()  # Wait for SessionClosed to be processed (persists summary) before stopping


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
